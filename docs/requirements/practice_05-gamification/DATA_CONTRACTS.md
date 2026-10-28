# Data Contracts

**Feature**: Игрификация задач: колесо фортуны и эмодзи
**Created**: 2026-10-28

## Entities

- User: name (unique), spins_remaining, last_reset_ref (UTC+offset policy), has_multi_emoji (bool), created_at/updated_at.
- EmojiCatalog: code (string), version (string), rarity (common/rare/very_rare), display_name, icon_ref.
- UserEmoji: user_name -> (emoji_code, emoji_version), granted_at.
- TaskEmoji: task_id -> [emoji_code, emoji_version] (up to 1 by default; up to 3 with multi-emoji perk).
- SpinHistory (optional): user_name, outcome_type (emoji/other), outcome_code, at.

## Invariants

- User.name is unique; attempts to rename to an existing name are rejected.
- At least one emoji must be present in every spin pool.
- Duplicated emoji outcomes: no change to UserEmoji; user is notified.
- Multi-emoji enables up to 3 emojis per task; otherwise only 1.
