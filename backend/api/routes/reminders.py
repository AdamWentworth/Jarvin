from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import (
    ReminderCreateRequest,
    ReminderItem,
    ReminderListResponse,
    ReminderUpdateRequest,
)
from memory.reminders import (
    create_reminder,
    delete_reminder,
    get_reminder,
    list_due_reminders,
    list_reminders,
    update_reminder,
    complete_reminder,
)

router = APIRouter(tags=["reminders"])


def _to_item(record: dict[str, object]) -> ReminderItem:
    return ReminderItem(
        id=int(record["id"]),
        title=str(record["title"]),
        notes=str(record.get("notes") or ""),
        due_at=str(record["due_at"]),
        recurrence=str(record.get("recurrence") or "once"),
        status=str(record.get("status") or "pending"),
        created_at=str(record.get("created_at") or "") or None,
        updated_at=str(record.get("updated_at") or "") or None,
        completed_at=str(record.get("completed_at") or "") or None,
        is_routine=bool(record.get("is_routine")),
        is_overdue=bool(record.get("is_overdue")),
    )


def _list_response(items: list[dict[str, object]]) -> ReminderListResponse:
    return ReminderListResponse(reminders=[_to_item(item) for item in items])


def _translate_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    lowered = message.lower()
    if "does not exist" in lowered:
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.get("/reminders", response_model=ReminderListResponse)
async def reminders_list(
    status: str | None = "pending",
    recurrence: str | None = None,
    limit: int = 50,
) -> ReminderListResponse:
    try:
        return _list_response(
            list_reminders(
                status=status,
                recurrence=recurrence,
                limit=limit,
            )
        )
    except ValueError as exc:
        raise _translate_error(exc) from exc


@router.get("/reminders/due", response_model=ReminderListResponse)
async def due_reminders(minutes_ahead: int = 15, limit: int = 20) -> ReminderListResponse:
    try:
        return _list_response(list_due_reminders(minutes_ahead=minutes_ahead, limit=limit))
    except ValueError as exc:
        raise _translate_error(exc) from exc


@router.get("/reminders/{reminder_id}", response_model=ReminderItem)
async def get_reminder_route(reminder_id: int) -> ReminderItem:
    try:
        return _to_item(get_reminder(reminder_id))
    except ValueError as exc:
        raise _translate_error(exc) from exc


@router.post("/reminders", response_model=ReminderItem)
async def create_reminder_route(payload: ReminderCreateRequest) -> ReminderItem:
    try:
        reminder = create_reminder(
            payload.title,
            due_at=payload.due_at,
            recurrence=payload.recurrence,
            notes=payload.notes,
        )
        return _to_item(reminder)
    except ValueError as exc:
        raise _translate_error(exc) from exc


@router.patch("/reminders/{reminder_id}", response_model=ReminderItem)
async def update_reminder_route(reminder_id: int, payload: ReminderUpdateRequest) -> ReminderItem:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No reminder fields were provided.")
    try:
        return _to_item(update_reminder(reminder_id, **updates))
    except ValueError as exc:
        raise _translate_error(exc) from exc


@router.post("/reminders/{reminder_id}/complete", response_model=ReminderItem)
async def complete_reminder_route(reminder_id: int) -> ReminderItem:
    try:
        return _to_item(complete_reminder(reminder_id))
    except ValueError as exc:
        raise _translate_error(exc) from exc


@router.delete("/reminders/{reminder_id}", response_model=ReminderItem)
async def delete_reminder_route(reminder_id: int) -> ReminderItem:
    try:
        return _to_item(delete_reminder(reminder_id))
    except ValueError as exc:
        raise _translate_error(exc) from exc
