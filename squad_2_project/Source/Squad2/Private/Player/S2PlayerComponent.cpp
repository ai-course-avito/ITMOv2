#include "Player/S2PlayerComponent.h"

#include "EnhancedInputComponent.h"
#include "Player/S2PlayerController.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

US2PlayerComponent::US2PlayerComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	PendingForward = 0.f;
	PendingRight = 0.f;
}

void US2PlayerComponent::BeginPlay()
{
	Super::BeginPlay();
}

void US2PlayerComponent::BindInput(UInputComponent* Input, AController* Controller)
{
	CachedPC = Cast<AS2PlayerController>(Controller);
	if (!IsValid(CachedPC))
	{
		return;
	}

	UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(Input);
	if (!EIC)
	{
		return;
	}

	EIC->BindAction(CachedPC->GetMoveForwardAction(), ETriggerEvent::Triggered, this, &US2PlayerComponent::OnMoveForward);
	EIC->BindAction(CachedPC->GetMoveRightAction(), ETriggerEvent::Triggered, this, &US2PlayerComponent::OnMoveRight);
	EIC->BindAction(CachedPC->GetFireAction(), ETriggerEvent::Started, this, &US2PlayerComponent::OnFireStarted);
}

void US2PlayerComponent::OnMoveForward(const FInputActionInstance& Instance)
{
	PendingForward = Instance.GetValue().Get<float>();
	ApplyMovement();
}

void US2PlayerComponent::OnMoveRight(const FInputActionInstance& Instance)
{
	PendingRight = Instance.GetValue().Get<float>();
	ApplyMovement();
}

void US2PlayerComponent::ApplyMovement()
{
	ACharacter* Char = Cast<ACharacter>(GetOwner());
	if (!Char)
	{
		return;
	}
	if (UCharacterMovementComponent* Move = Char->GetCharacterMovement())
	{
		FVector Forward = FVector::ForwardVector;
		FVector Right = FVector::RightVector;
		Char->AddMovementInput(Forward, PendingForward);
		Char->AddMovementInput(Right, PendingRight);
	}
}

void US2PlayerComponent::OnFireStarted(const FInputActionInstance& Instance)
{
	UE_LOG(LogS2, Log, TEXT("Fire!"));
}
