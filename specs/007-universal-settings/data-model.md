# Data Model: Universal App Settings

**Feature**: 007-universal-settings
**Date**: 2026-03-16

## Entity: UserSettings

### DB Table: `user_settings`

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `INTEGER` | PRIMARY KEY | `1` | Always 1; single-row table |
| `display_name` | `VARCHAR(255)` | nullable | `NULL` | User's preferred name |
| `language_code` | `VARCHAR(10)` | NOT NULL | `'en'` | BCP 47 tag, e.g. `"fr"` |
| `ai_instructions` | `TEXT` | nullable | `NULL` | Up to 2,000 chars; validated in Pydantic |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL | `now()` | Auto-updated on write |

### SQLAlchemy ORM (`src/writer/models/db.py`)

```python
class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    ai_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

### Pydantic Schemas (`src/writer/models/schemas.py`)

```python
class UserSettingsUpdate(BaseModel):
    display_name: str | None = None
    language_code: str = "en"
    ai_instructions: Annotated[str | None, Field(max_length=2000)] = None

class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None
    language_code: str
    ai_instructions: str | None
    updated_at: datetime
```

## Access Patterns

| Operation | Where | Notes |
|-----------|-------|-------|
| Get settings | `settings_service.get_settings(db)` | Returns defaults if row missing |
| Upsert settings | `settings_service.upsert_settings(db, data)` | Single-row upsert (id=1) |
| Inject into agent | `chat_service.invoke_chat_agent(…, user_settings)` | Passed to `make_chat_agent` |

## Supported Languages (initial list)

| Code | Label |
|------|-------|
| `en` | English |
| `en-GB` | English (UK) |
| `fr` | French |
| `de` | German |
| `es` | Spanish |
| `it` | Italian |
| `pt` | Portuguese |
| `nl` | Dutch |
| `ja` | Japanese |
| `zh` | Chinese (Simplified) |
| `ar` | Arabic |

Static dict in `settings_service.py`; no separate DB table needed.
