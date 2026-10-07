#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "S2PlayerPawn.generated.h"

class UCameraComponent;
class USpringArmComponent;
class US2PlayerComponent;

UCLASS()
class AS2PlayerPawn : public ACharacter
{
	GENERATED_BODY()

public:
	AS2PlayerPawn();

protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

private:
	UPROPERTY(VisibleAnywhere, Category = "Camera")
	USpringArmComponent* CameraBoom;

	UPROPERTY(VisibleAnywhere, Category = "Camera")
	UCameraComponent* TopDownCamera;

	UPROPERTY(VisibleAnywhere, Category = "Input")
	US2PlayerComponent* PlayerComponent;
};
