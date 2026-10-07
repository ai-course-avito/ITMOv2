#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InputActionValue.h"
#include "S2PlayerComponent.generated.h"

class UInputComponent;
class UEnhancedInputComponent;
class AS2PlayerController;

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class US2PlayerComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	US2PlayerComponent();

protected:
	virtual void BeginPlay() override;

public:
	// Called from Pawn::SetupPlayerInputComponent
	void BindInput(UInputComponent* Input, AController* Controller);

private:

	void OnMoveForward(const FInputActionInstance& Instance);
	void OnMoveRight(const FInputActionInstance& Instance);
	void OnFireStarted(const FInputActionInstance& Instance);

	UFUNCTION()
	void ApplyMovement();

	UPROPERTY()
	AS2PlayerController* CachedPC;

	UPROPERTY()
	float PendingForward;

	UPROPERTY()
	float PendingRight;
};
