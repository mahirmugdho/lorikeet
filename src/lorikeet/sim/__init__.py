"""Play Lorikeet without a camera: simulated sticky notes stand in for real ones.

The sim is an input choice, like the camera. It produces the same `Scene`s through the same
`SceneSource` protocol (ADR 0004), so a game can't tell which one it's running on.
"""
