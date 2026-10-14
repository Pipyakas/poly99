#pragma once

#include "Subsystems/WorldSubsystem.h"
#include "Poly99Simulation.generated.h"

UENUM(BlueprintType)
enum class EPoly99EntityType : uint8
{
	None = 0,
	Player,
	Bullet,
	EnemyGrasshopper,
	EnemyWanderer
};

/** Mirrors Poly99EventType (core_api.h). */
UENUM(BlueprintType)
enum class EPoly99EventType : uint8
{
	EnemyKilled = 0,
	PlayerHit,
	PlayerDash,
	BulletFired,
	WaveStart,
	GameOver
};

USTRUCT(BlueprintType)
struct POLY99CORE_API FPoly99EventView
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	EPoly99EventType Type = EPoly99EventType::EnemyKilled;

	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	FVector Location = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	EPoly99EntityType EntityType = EPoly99EntityType::None;

	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	FColor Color = FColor::White;
};

/** Mirrors Poly99Config (core_api.h). Defaults match raylib/config.cpp. */
USTRUCT(BlueprintType)
struct POLY99CORE_API FPoly99CoreConfig
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float PlayerSpeed = 300.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float PlayerRadius = 14.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") int32 PlayerLives = 3;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float BulletSpeed = 700.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float BulletRadius = 4.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float FireCooldown = 0.12f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float EnemySpeed = 130.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float EnemyRadius = 15.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") int32 EnemySpawnCap = 10;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float SpawnInterval = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float SpawnIntervalMin = 0.25f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float WaveDuration = 30.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float InvulnTime = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") FColor PlayerColor = FColor(255, 255, 255);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") FColor BulletColor = FColor(57, 255, 20);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") FColor EnemyColor = FColor(255, 59, 59);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float DashSpeed = 1100.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float DashDuration = 0.14f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float DashCooldown = 0.8f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float WandererSpeed = 90.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") float WandererRadius = 20.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99") FColor WandererColor = FColor(255, 176, 0);
};

USTRUCT(BlueprintType)
struct POLY99CORE_API FPoly99EntityView
{
	GENERATED_BODY()

	/** World-space location on the arena plane (Z = 0). */
	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	FVector Location = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	FVector Velocity = FVector::ZeroVector;

	/** World yaw in degrees. */
	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	float Yaw = 0.f;

	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	float Radius = 0.f;

	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	EPoly99EntityType Type = EPoly99EntityType::None;

	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	FColor Color = FColor::White;

	/** Index into the core entity pool; stable while the entity is alive. */
	UPROPERTY(BlueprintReadOnly, Category = "poly99")
	int32 PoolIndex = INDEX_NONE;
};

/**
 * Owns the single poly99 core instance for a game world and ticks it.
 * Core space is 2D (x right, y down). The arena is centred on the world
 * origin: world +Y = core +x (screen right), world +X = core -y (screen up).
 */
UCLASS()
class POLY99CORE_API UPoly99Simulation : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	/** The simulation for WorldContext's world (also usable from Python, which cannot reach world subsystems). */
	UFUNCTION(BlueprintPure, Category = "poly99", meta = (WorldContext = "WorldContext"))
	static UPoly99Simulation* Get(const UObject* WorldContext);

	/**
	 * Scripted input for automated tests/agents: while enabled, player-controller input is
	 * ignored and these values are fed to the core every tick (dash fires once per call).
	 */
	UFUNCTION(BlueprintCallable, Category = "poly99|Testing")
	void SetInputOverride(bool bEnable, FVector2D Move, FVector2D Aim, bool bFiring, bool bDash = false);

	/** Unreal units per core unit. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float UnitsPerCoreUnit = 2.f;

	UFUNCTION(BlueprintCallable, Category = "poly99")
	void StartSimulation(const FPoly99CoreConfig& Config, int32 Seed = 0, float ArenaWidth = 1280.f, float ArenaHeight = 720.f);

	UFUNCTION(BlueprintCallable, Category = "poly99")
	void StopSimulation();

	/** Move/aim in world axes (X forward, Y right), length <= 1. */
	UFUNCTION(BlueprintCallable, Category = "poly99")
	void SetInput(FVector2D Move, FVector2D Aim, bool bFiring, bool bDash = false);

	UFUNCTION(BlueprintPure, Category = "poly99")
	bool IsRunning() const { return bRunning; }

	UFUNCTION(BlueprintPure, Category = "poly99")
	const TArray<FPoly99EntityView>& GetEntities() const { return Entities; }

	/** Returns false when no player entity is alive. */
	UFUNCTION(BlueprintPure, Category = "poly99")
	bool GetPlayer(FPoly99EntityView& OutPlayer) const;

	/** Events produced by the most recent core tick (cleared every tick). */
	UFUNCTION(BlueprintPure, Category = "poly99")
	const TArray<FPoly99EventView>& GetEvents() const { return Events; }

	UFUNCTION(BlueprintPure, Category = "poly99")
	bool IsDashing() const { return bDashing; }

	UFUNCTION(BlueprintPure, Category = "poly99")
	float GetDashCooldownRemaining() const { return DashCooldownRemaining; }

	UFUNCTION(BlueprintPure, Category = "poly99")
	void GetStats(int32& OutScore, int32& OutWave, int32& OutLives, bool& bOutGameOver) const;

	UFUNCTION(BlueprintPure, Category = "poly99")
	FVector CoreToWorld(float X, float Y) const;

	/** Half-size of the arena in world units (X, Y). */
	UFUNCTION(BlueprintPure, Category = "poly99")
	FVector2D GetArenaHalfExtentWorld() const;

	// UTickableWorldSubsystem
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
	virtual void Deinitialize() override;

private:
	void RefreshSnapshot();

	bool bRunning = false;
	float ArenaW = 1280.f;
	float ArenaH = 720.f;
	FVector2D PendingMove = FVector2D::ZeroVector;
	FVector2D PendingAim = FVector2D::ZeroVector;
	bool bPendingFire = false;
	bool bPendingDash = false;
	bool bInputOverride = false;

	UPROPERTY(Transient)
	TArray<FPoly99EntityView> Entities;

	UPROPERTY(Transient)
	TArray<FPoly99EventView> Events;

	bool bDashing = false;
	float DashCooldownRemaining = 0.f;
	int32 Score = 0;
	int32 Wave = 0;
	int32 Lives = 0;
	bool bGameOver = false;
};
