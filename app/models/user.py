from dataclasses import dataclass


@dataclass
class UserStatus:
    telegram_id: int
    accepted_rules: bool
    questionnaire_completed: bool
    accepted_pd: bool
