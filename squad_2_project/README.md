Unreal Engine 5 C++ skeleton for a top-down solo shooter per AGENTS.md.

Structure:
- Squad2.uproject: UE5 project descriptor
- Source/Squad2: Primary module
- Config/DefaultEngine.ini: basic settings

Classes:
- AS2GameMode: sets default pawn, controller, HUD
- AS2PlayerPawn: Character with top-down camera
- AS2PlayerController: Enhanced Input context and actions created in C++
- US2PlayerComponent: binds input and drives movement
- AS2HUD + US2HUDWidget: minimal HUD via UMG (no textures)

Build with Unreal Editor 5.x. Open Squad2.uproject.
