from __future__ import annotations

import re

WEATHER_RE = re.compile(
    r"(?:what(?:'s| is)\s+the\s+weather|weather|forecast)(?:\s+(?:like|for|in|at))?\s+(?P<location>.+)$",
    re.IGNORECASE,
)
WEB_SEARCH_RE = re.compile(
    r"(?:(?:can you|could you|please)\s+)?(?:search(?:\s+the\s+web)?\s+for|look up|find information on)\s+(?P<query>.+)$",
    re.IGNORECASE,
)
GOOGLE_RE = re.compile(
    r"(?:(?:can you|could you|please)\s+)?google\s+(?P<query>.+)$",
    re.IGNORECASE,
)
CALENDAR_AUTH_RE = re.compile(
    r"(?:connect|set up|setup|authorize|auth|link).*(?:google\s+calendar|calendar)|(?:google\s+calendar|calendar).*(?:connect|set up|setup|authorize|auth|link)",
    re.IGNORECASE,
)
CALENDAR_LOOKUP_RE = re.compile(
    r"(?:what(?:'s| is)\s+on\s+(?:my\s+)?(?:calendar|schedule)|show\s+(?:my\s+)?(?:calendar|schedule)|(?:my\s+)?agenda\b|do i have anything\b)",
    re.IGNORECASE,
)
CALENDAR_DETAILS_RE = re.compile(
    r"(?:(?:show|read|open|view)\s+(?:me\s+)?(?:event(?:\s+details)?|details(?:\s+for)?)\s+)(?P<query>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
CALENDAR_DELETE_RE = re.compile(
    r"(?:(?:please\s+)?(?:delete|remove|cancel)\s+)(?P<query>.+?)(?:\s+(?:from|on)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
CALENDAR_RENAME_RE = re.compile(
    r"(?:(?:please\s+)?(?:rename|retitle)\s+)(?P<query>.+?)\s+(?:to|as)\s+(?P<new_title>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
CALENDAR_TITLE_RE = re.compile(
    r"(?:(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?title\s+(?:of|for)\s+)(?P<query>.+?)\s+to\s+(?P<new_title>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
CALENDAR_LOCATION_RE = re.compile(
    r"(?:(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?location\s+(?:of|for)\s+)(?P<query>.+?)\s+to\s+(?P<location>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
CALENDAR_CLEAR_LOCATION_RE = re.compile(
    r"(?:(?:please\s+)?(?:clear|remove|delete)\s+(?:the\s+)?location\s+(?:of|from)\s+)(?P<query>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
CALENDAR_NOTES_RE = re.compile(
    r"(?:(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?(?:notes|description)\s+(?:of|for)\s+)(?P<query>.+?)\s+to\s+(?P<description>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
CALENDAR_CLEAR_NOTES_RE = re.compile(
    r"(?:(?:please\s+)?(?:clear|remove|delete)\s+(?:the\s+)?(?:notes|description)\s+(?:of|from)\s+)(?P<query>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
CALENDAR_MOVE_RE = re.compile(
    r"(?:(?:please\s+)?(?:move|reschedule|change|update)\s+)(?P<query>.+?)\s+to\s+(?P<when>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
REPO_SEARCH_RE = re.compile(
    r"(?:(?:search|find)\s+(?:the\s+)?(?:repo|repository|codebase|workspace)\s+(?:for\s+)?)?(?P<query>.+?)\s+(?:in\s+(?:the\s+)?(?:repo|repository|codebase|workspace))$",
    re.IGNORECASE,
)
READ_FILE_RE = re.compile(
    r"(?:(?:read|open|show)\s+(?:me\s+)?)`?(?P<path>[\w./\\-]+\.[\w.-]+)`?(?:\s+lines?\s+(?P<start>\d+)(?:\s*(?:to|-)\s*(?P<end>\d+))?)?$",
    re.IGNORECASE,
)
LIST_DIR_RE = re.compile(
    r"(?:(?:list|show)\s+(?:files|contents)(?:\s+in)?\s+)(?P<path>[\w./\\-]+)$",
    re.IGNORECASE,
)
RUN_RE = re.compile(
    r"(?:(?:please\s+)?(?:run|execute))\s+(?P<command>.+)$",
    re.IGNORECASE,
)

CONFIRM_PATTERNS = {
    "yes",
    "y",
    "confirm",
    "go ahead",
    "do it",
    "please do",
    "okay",
    "ok",
    "sure",
}

CANCEL_PATTERNS = {
    "no",
    "n",
    "deny",
    "cancel",
    "stop",
    "never mind",
    "nevermind",
}
