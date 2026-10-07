#include "Player/S2PlayerController.h"

#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "GameFramework/Pawn.h"
#include "InputCoreTypes.h"
#include "InputModifiers.h"


AS2PlayerController::AS2PlayerController()
{
	// Default to no ticking per project rules
	PrimaryActorTick.bCanEverTick = false;

	// Create simple input assets in C++ so we don't depend on content
    UInputMappingContext* Mapping = NewObject<UInputMappingContext>(this, TEXT("S2_DefaultIMC"));
    DefaultMapping = Mapping;

    UInputAction* MoveF = NewObject<UInputAction>(this, TEXT("S2_MoveForwardIA"));
    MoveF->ValueType = EInputActionValueType::Axis1D;
    MoveForwardAction = MoveF;

    UInputAction* MoveR = NewObject<UInputAction>(this, TEXT("S2_MoveRightIA"));
    MoveR->ValueType = EInputActionValueType::Axis1D;
    MoveRightAction = MoveR;

    UInputAction* Fire = NewObject<UInputAction>(this, TEXT("S2_FireIA"));
    Fire->ValueType = EInputActionValueType::Boolean;
    FireAction = Fire;

    // Map basic keys without content assets
    if (DefaultMapping)
    {
        // Forward/Backward: W/S (S negated)
        DefaultMapping->MapKey(MoveForwardAction, EKeys::W);
        FEnhancedActionKeyMapping& MF_S = DefaultMapping->MapKey(MoveForwardAction, EKeys::S);
        MF_S.Modifiers.Add(NewObject<UInputModifierNegate>(this));

        // Right/Left: D/A (A negated)
        DefaultMapping->MapKey(MoveRightAction, EKeys::D);
        FEnhancedActionKeyMapping& MR_A = DefaultMapping->MapKey(MoveRightAction, EKeys::A);
        MR_A.Modifiers.Add(NewObject<UInputModifierNegate>(this));

        // Fire: Left Mouse Button
        DefaultMapping->MapKey(FireAction, EKeys::LeftMouseButton);
    }
}

void AS2PlayerController::BeginPlay()
{
	Super::BeginPlay();

	// Apply mapping context
    if (ULocalPlayer* LocalPlayer = GetLocalPlayer())
    {
        UEnhancedInputLocalPlayerSubsystem* Subsystem = LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>();
        if (IsValid(Subsystem) && IsValid(DefaultMapping))
        {
            Subsystem->AddMappingContext(DefaultMapping, /*Priority*/0);
        }
    }
}
