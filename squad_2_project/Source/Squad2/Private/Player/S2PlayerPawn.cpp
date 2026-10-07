#include "Player/S2PlayerPawn.h"

#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Player/S2PlayerComponent.h"

AS2PlayerPawn::AS2PlayerPawn()
{
	PrimaryActorTick.bCanEverTick = false;

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 600.f;
	CameraBoom->bDoCollisionTest = false;
	CameraBoom->SetRelativeRotation(FRotator(-60.f, 0.f, 0.f));

	TopDownCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("TopDownCamera"));
	TopDownCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	TopDownCamera->bUsePawnControlRotation = false;

	PlayerComponent = CreateDefaultSubobject<US2PlayerComponent>(TEXT("PlayerComponent"));
}

void AS2PlayerPawn::BeginPlay()
{
	Super::BeginPlay();
}

void AS2PlayerPawn::SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	if (PlayerComponent)
	{
		PlayerComponent->BindInput(PlayerInputComponent, Controller);
	}
}
