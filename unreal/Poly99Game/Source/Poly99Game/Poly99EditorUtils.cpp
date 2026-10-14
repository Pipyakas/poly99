#include "Poly99EditorUtils.h"

#include "Animation/AnimSequence.h"
#include "Animation/BlendSpace.h"

void UPoly99EditorUtils::NotifyAssetChanged(UObject* Asset)
{
#if WITH_EDITOR
	if (Asset)
	{
		Asset->PreEditChange(nullptr);
		Asset->PostEditChange();
		Asset->MarkPackageDirty();
	}
#endif
}

int32 UPoly99EditorUtils::BuildBlendSpace(UBlendSpace* BlendSpace, const TArray<UAnimSequence*>& Animations, const TArray<FVector>& SampleValues)
{
	int32 Added = 0;
#if WITH_EDITOR
	if (!BlendSpace || Animations.Num() != SampleValues.Num())
	{
		return 0;
	}
	BlendSpace->Modify();
	while (BlendSpace->GetNumberOfBlendSamples() > 0)
	{
		BlendSpace->DeleteSample(BlendSpace->GetNumberOfBlendSamples() - 1);
	}
	for (int32 i = 0; i < Animations.Num(); ++i)
	{
		if (Animations[i] && BlendSpace->AddSample(Animations[i], SampleValues[i]) != INDEX_NONE)
		{
			++Added;
		}
	}
	BlendSpace->ValidateSampleData();
	BlendSpace->ResampleData();
	BlendSpace->MarkPackageDirty();
#endif
	return Added;
}
