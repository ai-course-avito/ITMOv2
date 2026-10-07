// Copyright (c) Squad2
using UnrealBuildTool;

public class Squad2Target : TargetRules
{
	public Squad2Target(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_3;
		ExtraModuleNames.Add("Squad2");
	}
}
