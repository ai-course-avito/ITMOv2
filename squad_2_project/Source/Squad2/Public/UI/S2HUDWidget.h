#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "S2HUDWidget.generated.h"

class UProgressBar;
class UTextBlock;
class UVerticalBox;
class UVerticalBoxSlot;
class UWidgetTree;

UCLASS()
class US2HUDWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual void NativeConstruct() override;

private:
	UPROPERTY()
	UTextBlock* StatusText;

	UPROPERTY()
	UProgressBar* HealthBar;
};
