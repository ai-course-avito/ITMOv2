#include "UI/S2HUDWidget.h"

#include "Components/ProgressBar.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "WidgetTree.h"

void US2HUDWidget::NativeConstruct()
{
	Super::NativeConstruct();

	// Build a minimal widget tree in code: vertical box with text and progress bar
	// Note: For a production UI, use a .uasset via UMG Designer. Here we avoid textures and content deps.
	UWidgetTree* Tree = WidgetTree;
	if (!Tree)
	{
		return;
	}

	UVerticalBox* RootBox = NewObject<UVerticalBox>(this, UVerticalBox::StaticClass());
	Tree->RootWidget = RootBox;

	UTextBlock* Text = NewObject<UTextBlock>(this);
	Text->SetText(FText::FromString(TEXT("Top-Down Shooter")));
	Text->SetJustification(ETextJustify::Center);
	StatusText = Text;

	UVerticalBoxSlot* TextSlot = RootBox->AddChildToVerticalBox(Text);
	TextSlot->SetHorizontalAlignment(HAlign_Fill);
	TextSlot->SetPadding(FMargin(8.f));

	UProgressBar* Bar = NewObject<UProgressBar>(this);
	Bar->SetPercent(1.0f);
	HealthBar = Bar;

	UVerticalBoxSlot* BarSlot = RootBox->AddChildToVerticalBox(Bar);
	BarSlot->SetPadding(FMargin(8.f));
}
