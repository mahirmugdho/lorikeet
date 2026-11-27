#version 330

// The clay vertex shader: places each vertex, and gives the fragment shader what it needs
// to light it. The one thing it changes is "boil" (see below).

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat3 p3d_NormalMatrix;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;  // rgb: a tint for the clay's colour (white on figures); a: baked occlusion
// How far this vertex is from each of up to 12 clays (see ClayMesh.clay_distances).
in vec4 clay_a;
in vec4 clay_b;
in vec4 clay_c;

// Boil: in stop-motion every frame is a new photo of clay that's been handled since the
// last one, so the surface creeps very slightly from frame to frame. We fake that by
// pushing each vertex in or out along its normal by smooth noise, and changing the noise
// about 12 times a second (boil_seed is a whole number that ticks up on each step).
// Positions and turns still move at the full 60 fps; only this creep is stepped.
uniform float boil_amount;  // pixels, at most
uniform float boil_seed;

out vec3 v_world_pos;
out vec3 v_world_normal;
out vec3 v_view_pos;
out vec3 v_view_normal;
out vec3 v_object_pos;
out vec3 v_object_normal;
out vec4 v_colour;
out vec4 v_clay_a;
out vec4 v_clay_b;
out vec4 v_clay_c;

float hash(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

// Smooth value noise, -1 to 1: random values on a lattice, blended with a smooth curve.
float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash(i + vec3(0, 0, 0)), hash(i + vec3(1, 0, 0)), f.x),
                   mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y),
               mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x),
                   mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1, 1, 1)), f.x), f.y),
               f.z) * 2.0 - 1.0;
}

void main() {
    vec3 normal = normalize(p3d_Normal);
    vec3 pos = p3d_Vertex.xyz;
    if (boil_amount > 0.0) {
        // Each boil step jumps to an unrelated patch of noise; lumps about 12 px apart.
        vec3 jump = vec3(17.13, 31.71, 7.37) * boil_seed;
        pos += normal * boil_amount * noise(pos / 12.0 + jump);
    }
    vec4 here = vec4(pos, 1.0);
    gl_Position = p3d_ModelViewProjectionMatrix * here;
    v_world_pos = (p3d_ModelMatrix * here).xyz;
    v_world_normal = normalize(mat3(p3d_ModelMatrix) * normal);
    v_view_pos = (p3d_ModelViewMatrix * here).xyz;
    v_view_normal = normalize(p3d_NormalMatrix * normal);
    // The original, unboiled position for the texture, so fingerprints don't swim.
    v_object_pos = p3d_Vertex.xyz;
    v_object_normal = normal;
    v_colour = p3d_Color;
    v_clay_a = clay_a;
    v_clay_b = clay_b;
    v_clay_c = clay_c;
}
