#include "Game/S2GameMode.h"
#include "Player/S2PlayerController.h"
#include "Player/S2PlayerPawn.h"
#include "UI/S2HUD.h"

AS2GameMode::AS2GameMode()
{
	PlayerControllerClass = AS2PlayerController::StaticClass();
	DefaultPawnClass = AS2PlayerPawn::StaticClass();
	HUDClass = AS2HUD::StaticClass();
}
