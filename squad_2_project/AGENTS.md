# agents.md

## Проект
Разработка игры/проекта на **Unreal Engine 5.x** с использованием **C++**.
Основной язык логики — C++, Blueprint — только для связки, UI и контента.
Цель: чистый, производительный, стандарт-совместимый код Epic Games.
Сама игра: вид сверху, соло игра стрелять против ботов, доступная техника.

## Стек
- **Движок**: Unreal Engine 5.x (НЕ UE4, НЕ UE3)
- **Язык**: C++ (стандарт движка: C++20 в UE5.3+, C++17 в UE5.0–5.2)
- **Сборка**: Unreal Build Tool (UBT), `.Build.cs`, `.Target.cs`
- **Редактор**: Unreal Editor 5.x
- **Система контроля версий**: Git + Git LFS (для `.uasset`, `.umap`)
- **IDE**: Rider for Unreal / Visual Studio 2022 / VS Code
- **UI**: UMG (Blueprint) + Slate (C++) для сложных виджетов
- **Input**: Enhanced Input System (НЕ legacy Input)
- **Сеть**: встроенный replication, без сторонних библиотек

## Соглашения по коду (Epic Games Standard)

### Именование (строго)
- Шаблоны: `T` — `TArray`, `TMap`, `TStrongObjectPtr`
- UObject: `U` — `UHealthComponent`, `UGameInstance`
- Actor: `A` — `AMyCharacter`, `AGameMode`
- Slate-виджеты: `S` — `SHealthBar`
- Структуры: `F` — `FVector`, `FInventoryItem`
- Enums: `E` — `EWeaponState`, `EDamageType`
- Интерфейсы: `I` — `IInteractable`
- Булевы: `b` — `bIsDead`, `bCanJump`
- Приватные поля: без префикса `m_`, просто `Health`, `Speed`
- Функции/переменные: `PascalCase`
- Локальные переменные: `camelCase` или `PascalCase` (как в проекте)

### Форматирование
- Отступ: **табы** (стандарт Epic), размер 4
- Фигурные скобки: **Allman** (на новой строке)
- Максимальная длина строки: 120 символов
- Пробелы вокруг операторов
- Один класс — один `.h` + `.cpp` (или `.h` + `.cpp` + `.generated.h`)

## Обязательные правила

### UObject и Garbage Collection
- **Всегда** `UPROPERTY()` на `UObject*` полях — иначе GC удалит
- Для не-UObject контейнеров с UObject внутри — `UPROPERTY()` тоже нужен
- `TStrongObjectPtr<>` — только если объект вне UObject-графа
- Проверка: `IsValid(Obj)` вместо `Obj != nullptr` (учитывает pending kill)
- Никогда не хранить `UObject*` в сырых C++ структурах без UPROPERTY

### Рефлексия
- `UCLASS()`, `USTRUCT()`, `UENUM()`, `UFUNCTION()`, `UPROPERTY()` — по необходимости
- `BlueprintReadWrite` — минимально; по умолчанию `BlueprintReadOnly`
- `BlueprintCallable` — только для функций, реально нужных BP
- `meta = (AllowPrivateAccess = true)` — для приватных полей с доступом из BP
- `Category = "..."` — обязательно для всех BP-экспонированных полей

### Производительность
- **Tick отключён по умолчанию**: `PrimaryActorTick.bCanEverTick = false`
- Включать Tick только если реально нужно, иначе — таймеры/события
- `Cast<T>()` — не в hot loop, кэшировать в `BeginPlay`/`PostInitializeComponents`
- `F` структуры для data-heavy, не-UObject типов
- `TSoftObjectPtr` / `TSoftClassPtr` для тяжёлых ассетов
- `FName` вместо `FString` для идентификаторов
- `const&` для передачи тяжёлых объектов
- `MoveTemp` / `Forward` где уместно
- `Reserve()` для `TArray` при известном размере

### Компоненты
- Поиск компонентов — в `PostInitializeComponents()` или `BeginPlay()`, не в Tick
- Кэшировать указатели на компоненты в поля
- `check(Comp)` в dev-сборке для обязательных компонентов
- Композиция через компоненты, не наследование

### Интерфейсы
- `UINTERFACE(MinimalAPI, Blueprintable)` + `IIntenfaceName`
- Вызов: `IIInteractable::Execute_OnInteract(Target, this)`
- Проверка: `TargetActor->Implements<UInteractable>()`

### Асинхронная загрузка
- `TSoftObjectPtr` / `TSoftClassPtr` для больших ассетов
- `StreamableManager` для runtime-загрузки
- Не блокировать game thread синхронной загрузкой

## Запрещено

- **Использовать UE4-API**: `TObjectPtr` есть только в UE5, `Enhanced Input` — только UE5.1+
- **Писать Blueprint-only логику**, которую можно сделать в C++
- **`GetWorld()->GetFirstPlayerController()` без проверки на nullptr**
- **Сырые `new`/`delete` для UObject** — только `NewObject<>()`, `CreateDefaultSubobject<>()`
- **Хранить `UObject*` без `UPROPERTY()`**
- **`Cast<>()` в `Tick()`**
- **Tick без причины** — по умолчанию `bCanEverTick = false`
- **Хардкод путей к ассетам** — только через `ConstructorHelpers::FObjectFinder` или `TSoftObjectPtr`
- **Игнорировать `IsValid()`** перед вызовом методов UObject
- **Смешивать UE4 и UE5 синтаксис** (например, `GetWorld()->GetTimeSeconds()` vs новые API)
- **Писать код без `#include "*.generated.h"`** в конце includes
- **Изменять `*.generated.h` вручную**
- **Использовать `std::` контейнеры** вместо `TArray`, `TMap`, `TSet`
- **`std::string`** вместо `FString` / `FName` / `FText`
- **`printf` / `std::cout`** — только `UE_LOG`
- **`assert`** — только `check`, `checkf`, `ensure`
- **Смешивать `std::shared_ptr`** с UObject (кроме не-UObject типов)

