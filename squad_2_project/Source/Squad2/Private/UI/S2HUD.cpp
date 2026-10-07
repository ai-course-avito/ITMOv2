#include "UI/S2HUD.h"
#include "UI/S2HUDWidget.h"
#include "Blueprint/UserWidget.h"

AS2HUD::AS2HUD()
{
	PrimaryActorTick.bCanEverTick = false;
}

void AS2HUD::BeginPlay()
{
	Super::BeginPlay();

	if (UWorld* World = GetWorld())
	{
		HUDWidget = CreateWidget<US2HUDWidget>(World, US2HUDWidget::StaticClass());
		if (IsValid(HUDWidget))
		{
			HUDWidget->AddToViewport(0);
		}
	}
}
