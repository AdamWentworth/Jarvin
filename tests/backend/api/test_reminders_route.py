from __future__ import annotations

import pytest

import backend.api.routes.reminders as reminders_mod
from backend.api.schemas import ReminderCreateRequest, ReminderUpdateRequest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_create_reminder_route_returns_item(monkeypatch):
    monkeypatch.setattr(
        reminders_mod,
        "create_reminder",
        lambda title, due_at, recurrence="once", notes="": {
            "id": 7,
            "title": title,
            "notes": notes,
            "due_at": due_at,
            "recurrence": recurrence,
            "status": "pending",
            "created_at": "2026-04-04T09:00:00-07:00",
            "updated_at": "2026-04-04T09:00:00-07:00",
            "completed_at": None,
            "is_routine": recurrence != "once",
            "is_overdue": False,
        },
        raising=True,
    )

    payload = ReminderCreateRequest(
        title="Call mom",
        due_at="2026-04-05T17:00:00-07:00",
        recurrence="once",
        notes="Use the new phone number.",
    )
    response = await reminders_mod.create_reminder_route(payload)

    assert response.id == 7
    assert response.title == "Call mom"
    assert response.notes == "Use the new phone number."


@pytest.mark.asyncio
async def test_due_reminders_route_wraps_results(monkeypatch):
    monkeypatch.setattr(
        reminders_mod,
        "list_due_reminders",
        lambda minutes_ahead=15, limit=20: [
            {
                "id": 1,
                "title": "Leave for lunch",
                "notes": "",
                "due_at": "2026-04-04T12:00:00-07:00",
                "recurrence": "once",
                "status": "pending",
                "created_at": "2026-04-04T09:00:00-07:00",
                "updated_at": "2026-04-04T09:00:00-07:00",
                "completed_at": None,
                "is_routine": False,
                "is_overdue": False,
            }
        ],
        raising=True,
    )

    response = await reminders_mod.due_reminders(minutes_ahead=30)

    assert len(response.reminders) == 1
    assert response.reminders[0].title == "Leave for lunch"


@pytest.mark.asyncio
async def test_update_reminder_route_requires_changes():
    with pytest.raises(HTTPException) as excinfo:
        await reminders_mod.update_reminder_route(4, ReminderUpdateRequest())
    assert excinfo.value.detail == "No reminder fields were provided."


@pytest.mark.asyncio
async def test_complete_reminder_route_returns_updated_item(monkeypatch):
    monkeypatch.setattr(
        reminders_mod,
        "complete_reminder",
        lambda reminder_id: {
            "id": reminder_id,
            "title": "Stretch",
            "notes": "",
            "due_at": "2026-04-05T08:00:00-07:00",
            "recurrence": "daily",
            "status": "pending",
            "created_at": "2026-04-04T09:00:00-07:00",
            "updated_at": "2026-04-04T10:00:00-07:00",
            "completed_at": "2026-04-04T10:00:00-07:00",
            "is_routine": True,
            "is_overdue": False,
        },
        raising=True,
    )

    response = await reminders_mod.complete_reminder_route(3)

    assert response.id == 3
    assert response.recurrence == "daily"
