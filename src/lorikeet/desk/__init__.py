"""Desk play: Lorikeet without a projector or camera.

Players who don't have the rig play on their screen at their desk. They drag sticky notes
onto the game with the mouse instead of sticking real ones on a wall. The desk is an input
choice, like the camera: it produces the same `Scene`s through the same `SceneSource`
protocol (ADR 0004), so a game can't tell which one it's running on.
"""
