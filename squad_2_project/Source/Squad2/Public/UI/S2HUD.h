#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "S2HUD.generated.h"

class US2HUDWidget;

UCLASS()
class AS2HUD : public AHUD
{
	GENERATED_BODY()

public:
	AS2HUD();

protected:
	virtual void BeginPlay() override;

private:
	UPROPERTY()
	US2HUDWidget* HUDWidget;
};
