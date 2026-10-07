#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "S2PlayerController.generated.h"

class UInputMappingContext;
class UInputAction;

UCLASS()
class AS2PlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	AS2PlayerController();

protected:
	virtual void BeginPlay() override;

private:
	// Enhanced Input assets set in C++ for a minimal setup
	UPROPERTY()
	UInputMappingContext* DefaultMapping;

	UPROPERTY()
	UInputAction* MoveForwardAction;

	UPROPERTY()
	UInputAction* MoveRightAction;

	UPROPERTY()
	UInputAction* FireAction;

public:
	UInputAction* GetMoveForwardAction() const { return MoveForwardAction; }
	UInputAction* GetMoveRightAction() const { return MoveRightAction; }
	UInputAction* GetFireAction() const { return FireAction; }
	UInputMappingContext* GetDefaultMapping() const { return DefaultMapping; }
};
