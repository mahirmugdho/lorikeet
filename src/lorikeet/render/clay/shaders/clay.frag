#version 330

// The clay fragment shader: lights each pixel of a figure (or the backdrop) so it reads as
// matte plasticine under a big soft studio light. All the lighting is done in linear light
// (see colour.py) and turned into sRGB only at the end, so colours stay vivid and soft
// gradients stay soft.
//
// The recipe, in the order it happens below:
//  0. Which clay this pixel is, from the distances to each clay.
//  1. Fine surface detail (fingerprints, smudges, cracks) tilts the normal a little.
//  2. Key light: one big soft light, with "wrap" so light creeps past the edge of the lit
//     side instead of stopping in a hard line, and a soft shadow from the shadow map.
//  3. Light that sinks in: just where the lit side turns away, the light takes on a
//     warmer, more saturated version of the clay's colour, as light that soaks into clay
//     comes back out a little way off, tinted by the clay. It changes the colour there,
//     not the brightness, so the form still shades.
//  4. Fill: soft light from all around (more from above than below) plus a gentle light
//     from the front right, darkened in creases by the baked occlusion. The fill uses a
//     more saturated version of the clay's colour, so shadows are colourful, not grey.
//  5. Sheen: a very broad, faint highlight. A small bright one would read as plastic.
//  6. Out: a soft roll-off towards white, sRGB, and a tiny bit of noise (dither) so smooth
//     gradients don't show 8-bit steps (banding).

uniform struct p3d_LightSourceParameters {
    vec4 color;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;  // view space -> shadow map (0-1 across the map, and 0-1 depth)
} p3d_LightSource[1];

uniform vec3 key_toward;      // world space, unit: the direction the key light comes from
uniform vec3 fill_toward;     // world space, unit: the gentle front fill
uniform vec3 fill_colour;
uniform vec3 sky_colour;      // soft all-round light from above...
uniform vec3 ground_colour;   // ...and from below: dimmer and warmer, as if off a floor

uniform sampler2D detail;     // rg: slopes, b: crack depth, a: sheen (see detail.py)
uniform float detail_tile;    // pixels of surface per texture tile
uniform float detail_strength;  // 1 for clay figures, less for the smooth backdrop

uniform float shadow_radius;  // how soft shadows landing on this are, in shadow map units
uniform float shadow_bias;    // in shadow map depth units
uniform float normal_offset;  // pixels: step out along the normal before looking up

uniform float sheen_strength;
uniform float shadow_strength;  // 1: a full shadow blocks all the key light; less lets some by
uniform vec3 palette[12];     // each clay's colour, linear light
uniform int debug_view;       // look-dev only: 0 the clay, 1 normals, 2 key light, 3 occlusion

in vec3 v_world_pos;
in vec3 v_world_normal;
in vec3 v_view_pos;
in vec3 v_view_normal;
in vec3 v_object_pos;
in vec3 v_object_normal;
in vec4 v_colour;
in vec4 v_clay_a;
in vec4 v_clay_b;
in vec4 v_clay_c;

out vec4 frag_colour;

const float WRAP = 0.25;  // how far past the edge the key light creeps (0 = not at all)
const vec3 TO_CAMERA = vec3(0.0, -1.0, 0.0);  // orthographic: the same everywhere

float luminance(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

vec3 saturate_colour(vec3 c, float amount) {
    // Push a colour away from the grey of the same brightness.
    return max(mix(vec3(luminance(c)), c, amount), 0.0);
}

// Interleaved gradient noise: a cheap, well-spread random number per screen pixel.
float pixel_noise(vec2 pixel) {
    return fract(52.9829189 * fract(dot(pixel, vec2(0.06711056, 0.00583715))));
}

// 0. Clay colour. The distances to each clay are blended smoothly across each triangle, so
// the nearest clay changes along a smooth curve, not along the triangles' edges. Right at
// the line, the two clays are mixed over about one pixel, so it's anti-aliased: smooth,
// but as crisp as the screen allows.
vec3 clay_colour() {
    float d[12] = float[](v_clay_a.x, v_clay_a.y, v_clay_a.z, v_clay_a.w,
                          v_clay_b.x, v_clay_b.y, v_clay_b.z, v_clay_b.w,
                          v_clay_c.x, v_clay_c.y, v_clay_c.z, v_clay_c.w);
    int nearest = 0, next = 1;
    float d1 = d[0], d2 = 1e9;
    for (int i = 1; i < 12; i++) {
        if (d[i] < d1) { d2 = d1; next = nearest; d1 = d[i]; nearest = i; }
        else if (d[i] < d2) { d2 = d[i]; next = i; }
    }
    float gap = d2 - d1;  // 0 on the line between the two clays
    float pixel = max(fwidth(gap), 1e-5);  // how much the gap changes across one pixel
    float mine = 0.5 + 0.5 * clamp(gap / pixel, 0.0, 1.0);
    return mix(palette[next], palette[nearest], mine);
}

// 1. Detail. The texture tiles in a flat plane, but figures are round, so it's projected
// three ways (along x, y and z: "triplanar") and the three are blended by how squarely the
// surface faces each axis. Each projection's slopes tilt the normal along its own two axes.
vec4 sample_detail(vec3 p, vec3 n, out vec3 tilt) {
    vec3 w = pow(abs(n), vec3(4.0));
    w /= (w.x + w.y + w.z);
    vec2 uv_x = p.yz / detail_tile + vec2(0.37, 0.11);
    vec2 uv_y = p.xz / detail_tile + vec2(0.71, 0.53);
    vec2 uv_z = p.xy / detail_tile + vec2(0.19, 0.83);
    vec4 tx = texture(detail, uv_x);
    vec4 ty = texture(detail, uv_y);
    vec4 tz = texture(detail, uv_z);
    tilt = w.x * vec3(0.0, tx.r, tx.g) + w.y * vec3(ty.r, 0.0, ty.g) + w.z * vec3(tz.r, tz.g, 0.0);
    return w.x * tx + w.y * ty + w.z * tz;
}

// 2. Soft shadow: percentage-closer filtering (PCF). Instead of one lookup (in shadow or
// not, which gives a hard, blocky edge) take 32 lookups spread over a disc and average
// them. They're laid out in a "Vogel" spiral (each one turned by the golden angle from the
// last), which covers a disc evenly with no rows to line up. The spiral is turned by a
// different random angle at every pixel, so the samples don't print visible copies of the
// edge; the faint grain left over is far less visible than banding would be. Each lookup
// is itself filtered by the hardware between four texels, so edges are smooth close up.
const int TAPS = 32;

float key_shadow(vec3 view_pos, vec3 view_normal) {
    // Step out a little along the normal first, so a surface never shadows itself from
    // rounding error ("shadow acne"). A step along the normal moves the lookup off the
    // surface without moving it sideways across the shadow's edge, which a plain depth
    // bias would need to be much bigger to do, and a big bias detaches shadows from
    // whatever casts them.
    vec4 at = p3d_LightSource[0].shadowViewMatrix * vec4(view_pos + view_normal * normal_offset, 1.0);
    vec3 coord = at.xyz / at.w;
    float angle = 6.2831853 * pixel_noise(gl_FragCoord.xy);
    mat2 turn = mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
    float lit = 0.0;
    for (int i = 0; i < TAPS; i++) {
        float r = sqrt((float(i) + 0.5) / float(TAPS));
        float a = float(i) * 2.39996323;  // the golden angle, in radians
        vec2 offset = turn * vec2(cos(a), sin(a)) * r * shadow_radius;
        lit += texture(p3d_LightSource[0].shadowMap, vec3(coord.xy + offset, coord.z - shadow_bias));
    }
    return lit / float(TAPS);
}

void main() {
    vec3 albedo = v_colour.rgb * clay_colour();
    float occlusion = v_colour.a;

    vec3 n = normalize(v_world_normal);
    vec4 d = vec4(0.0);
    if (detail_strength > 0.0) {  // the same for a whole object, so skipping is cheap
        vec3 tilt;
        d = sample_detail(v_object_pos, normalize(v_object_normal), tilt);
        // Tilt the normal by the slopes, keeping only the part along the surface.
        vec3 along = tilt - n * dot(tilt, n);
        n = normalize(n - detail_strength * along);
    }
    float crack = d.b * detail_strength;
    albedo *= 1.0 - 0.45 * crack;
    occlusion *= 1.0 - 0.5 * crack;

    // 2. Key light.
    vec3 key = p3d_LightSource[0].color.rgb;
    float facing = dot(n, key_toward);
    float wrapped = max((facing + WRAP) / (1.0 + WRAP), 0.0);
    float shadow = key_shadow(v_view_pos, normalize(v_view_normal));
    // The shadow map also "shadows" the far side of every round shape, where it turns away
    // from the light. The wrap already darkens that side softly, so let the shadow map have
    // its say only where the surface faces the light; otherwise it would draw a hard line
    // across the soft wrap.
    float geometric = dot(normalize(v_world_normal), key_toward);
    shadow = mix(1.0, shadow, smoothstep(-0.15, 0.3, geometric) * shadow_strength);
    vec3 lit = key * wrapped * shadow;
    // Creases are a little darker even in direct light: a big soft light still can't
    // reach all the way in.
    lit *= mix(1.0, occlusion, 0.35);

    // 3. Light that sinks in: a band around where the surface turns from the light.
    // saturate_colour keeps the brightness, and the warm shift is small, so the band
    // changes hue and richness only.
    vec3 rich = saturate_colour(albedo, 1.6) * vec3(1.06, 0.98, 0.92);
    float terminator = exp(-pow((facing - 0.1) / 0.3, 2.0));
    vec3 lit_colour = mix(albedo, rich, 0.7 * terminator);

    // 4. Fill: all-round light, more from above, plus a gentle front light.
    vec3 around = mix(ground_colour, sky_colour, n.z * 0.5 + 0.5);
    float fill_facing = max((dot(n, fill_toward) + WRAP) / (1.0 + WRAP), 0.0);
    vec3 fill = (around + fill_colour * fill_facing) * occlusion;
    vec3 shade = saturate_colour(albedo, 1.3);

    vec3 colour = lit_colour * lit + shade * fill;

    // 5. Sheen: broad and faint. The half-way vector between the light and the camera; the
    // low power (8) spreads the highlight wide, and it's never more than a few percent.
    vec3 half_way = normalize(key_toward + TO_CAMERA);
    float broad = pow(max(dot(n, half_way), 0.0), 8.0);
    float grazing = pow(1.0 - max(dot(n, TO_CAMERA), 0.0), 5.0);  // a touch more at edges
    float fresnel = 0.04 + 0.96 * grazing;
    float oily = 1.0 + d.a * detail_strength;
    colour += key * sheen_strength * oily * broad * fresnel * 2.5 * shadow * max(facing, 0.0);

    if (debug_view == 1) colour = pow(n * 0.5 + 0.5, vec3(2.2));
    if (debug_view == 2) colour = vec3(wrapped * shadow);
    if (debug_view == 3) colour = vec3(occlusion);

    // 6. Out. Above 0.6, roll off gently towards white instead of clipping hard. The
    // roll-off is wide and never flat, so even the brightest lit clay still shades from
    // its lit side to its edge; a hard clip would flatten bright colours into a sticker.
    vec3 over = max(colour - 0.6, 0.0);
    colour = min(colour, 0.6) + 0.4 * (1.0 - exp(-over / 0.4));
    // Linear light to sRGB, the exact curve.
    vec3 low = colour * 12.92;
    vec3 high = 1.055 * pow(colour, vec3(1.0 / 2.4)) - 0.055;
    vec3 encoded = mix(low, high, step(vec3(0.0031308), colour));
    // Dither: +-1 step of 8-bit noise, shaped so it averages out to nothing. Without it, a
    // slow gradient shows as visible bands one 8-bit step wide.
    float r1 = pixel_noise(gl_FragCoord.xy);
    float r2 = pixel_noise(gl_FragCoord.yx + 17.0);
    encoded += (r1 + r2 - 1.0) / 255.0;
    frag_colour = vec4(encoded, 1.0);
}
