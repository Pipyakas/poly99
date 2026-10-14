#include "Poly99Simulation.h"

#include "Engine/Engine.h"
#include "Engine/World.h"

THIRD_PARTY_INCLUDES_START
#include "core_api.h"
THIRD_PARTY_INCLUDES_END

namespace
{
	void CopyColor(const FColor& In, unsigned char Out[4])
	{
		Out[0] = In.R;
		Out[1] = In.G;
		Out[2] = In.B;
		Out[3] = In.A;
	}

	Poly99Config ToCore(const FPoly99CoreConfig& C)
	{
		Poly99Config Out = {};
		Out.playerSpeed = C.PlayerSpeed;
		Out.playerRadius = C.PlayerRadius;
		Out.playerLives = C.PlayerLives;
		Out.bulletSpeed = C.BulletSpeed;
		Out.bulletRadius = C.BulletRadius;
		Out.fireCooldown = C.FireCooldown;
		Out.enemySpeed = C.EnemySpeed;
		Out.enemyRadius = C.EnemyRadius;
		Out.enemySpawnCap = C.EnemySpawnCap;
		Out.spawnInterval = C.SpawnInterval;
		Out.spawnIntervalMin = C.SpawnIntervalMin;
		Out.waveDuration = C.WaveDuration;
		Out.invulnTime = C.InvulnTime;
		CopyColor(C.PlayerColor, Out.playerColor);
		CopyColor(C.BulletColor, Out.bulletColor);
		CopyColor(C.EnemyColor, Out.enemyColor);
		Out.dashSpeed = C.DashSpeed;
		Out.dashDuration = C.DashDuration;
		Out.dashCooldown = C.DashCooldown;
		Out.wandererSpeed = C.WandererSpeed;
		Out.wandererRadius = C.WandererRadius;
		CopyColor(C.WandererColor, Out.wandererColor);
		return Out;
	}
}

void UPoly99Simulation::StartSimulation(const FPoly99CoreConfig& Config, int32 Seed, float ArenaWidth, float ArenaHeight)
{
	if (bRunning)
	{
		poly99_shutdown();
	}
	ArenaW = ArenaWidth;
	ArenaH = ArenaHeight;
	const Poly99Config CoreConfig = ToCore(Config);
	poly99_init(static_cast<unsigned int>(Seed), &CoreConfig);
	poly99_set_arena(ArenaW, ArenaH);
	bRunning = true;
	RefreshSnapshot();
}

void UPoly99Simulation::StopSimulation()
{
	if (bRunning)
	{
		poly99_shutdown();
		bRunning = false;
	}
	Entities.Reset();
}

UPoly99Simulation* UPoly99Simulation::Get(const UObject* WorldContext)
{
	const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
	return World ? World->GetSubsystem<UPoly99Simulation>() : nullptr;
}

void UPoly99Simulation::SetInputOverride(bool bEnable, FVector2D Move, FVector2D Aim, bool bFiring, bool bDash)
{
	bInputOverride = false;
	SetInput(Move, Aim, bFiring, bDash);
	bInputOverride = bEnable;
}

void UPoly99Simulation::SetInput(FVector2D Move, FVector2D Aim, bool bFiring, bool bDash)
{
	if (bInputOverride)
	{
		return;
	}
	bPendingDash |= bDash;
	PendingMove = Move.GetClampedToMaxSize(1.f);
	PendingAim = Aim.GetClampedToMaxSize(1.f);
	bPendingFire = bFiring;
}

bool UPoly99Simulation::GetPlayer(FPoly99EntityView& OutPlayer) const
{
	for (const FPoly99EntityView& E : Entities)
	{
		if (E.Type == EPoly99EntityType::Player)
		{
			OutPlayer = E;
			return true;
		}
	}
	return false;
}

void UPoly99Simulation::GetStats(int32& OutScore, int32& OutWave, int32& OutLives, bool& bOutGameOver) const
{
	OutScore = Score;
	OutWave = Wave;
	OutLives = Lives;
	bOutGameOver = bGameOver;
}

FVector UPoly99Simulation::CoreToWorld(float X, float Y) const
{
	return FVector(-(Y - ArenaH * 0.5f) * UnitsPerCoreUnit, (X - ArenaW * 0.5f) * UnitsPerCoreUnit, 0.f);
}

FVector2D UPoly99Simulation::GetArenaHalfExtentWorld() const
{
	return FVector2D(ArenaH * 0.5f * UnitsPerCoreUnit, ArenaW * 0.5f * UnitsPerCoreUnit);
}

void UPoly99Simulation::Tick(float DeltaTime)
{
	if (!bRunning)
	{
		return;
	}
	// World (X forward, Y right) -> core (x right, y down)
	Poly99Input In = {};
	In.moveX = static_cast<float>(PendingMove.Y);
	In.moveY = static_cast<float>(-PendingMove.X);
	In.aimX = static_cast<float>(PendingAim.Y);
	In.aimY = static_cast<float>(-PendingAim.X);
	In.firing = bPendingFire ? 1 : 0;
	In.dash = bPendingDash ? 1 : 0;
	bPendingDash = false;
	poly99_tick(FMath::Min(DeltaTime, 0.1f), &In);
	RefreshSnapshot();
}

void UPoly99Simulation::RefreshSnapshot()
{
	Poly99Snapshot Snap = {};
	poly99_get_snapshot(&Snap);
	Score = Snap.score;
	Wave = Snap.wave;
	Lives = Snap.lives;
	bGameOver = Snap.gameOver != 0;
	bDashing = Snap.dashing != 0;
	DashCooldownRemaining = Snap.dashCooldownRemaining;

	Events.Reset(Snap.eventCount);
	for (int32 i = 0; i < Snap.eventCount; ++i)
	{
		const Poly99Event& Ev = Snap.events[i];
		FPoly99EventView& V = Events.AddDefaulted_GetRef();
		V.Type = static_cast<EPoly99EventType>(FMath::Clamp(Ev.type, 0, static_cast<int32>(EPoly99EventType::GameOver)));
		V.Location = CoreToWorld(Ev.x, Ev.y);
		V.EntityType = static_cast<EPoly99EntityType>(FMath::Clamp(Ev.entityType, 0, static_cast<int32>(EPoly99EntityType::EnemyWanderer)));
		V.Color = FColor(Ev.r, Ev.g, Ev.b, Ev.a);
	}

	Entities.Reset(Snap.entityCount);
	for (int32 i = 0; i < Snap.entityCount; ++i)
	{
		const Poly99Entity& E = Snap.entities[i];
		if (!E.alive)
		{
			continue;
		}
		FPoly99EntityView& V = Entities.AddDefaulted_GetRef();
		V.Location = CoreToWorld(E.x, E.y);
		V.Velocity = FVector(-E.vy, E.vx, 0.f) * UnitsPerCoreUnit;
		// core rot is atan2(y, x) in screen space; world yaw = atan2(worldY, worldX)
		V.Yaw = FMath::RadiansToDegrees(FMath::Atan2(FMath::Cos(E.rot), -FMath::Sin(E.rot)));
		V.Radius = E.radius * UnitsPerCoreUnit;
		V.Type = static_cast<EPoly99EntityType>(FMath::Clamp(E.type, 0, static_cast<int32>(EPoly99EntityType::EnemyWanderer)));
		V.Color = FColor(E.r, E.g, E.b, E.a);
		V.PoolIndex = i;
	}
}

TStatId UPoly99Simulation::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UPoly99Simulation, STATGROUP_Tickables);
}

bool UPoly99Simulation::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UPoly99Simulation::Deinitialize()
{
	StopSimulation();
	Super::Deinitialize();
}
