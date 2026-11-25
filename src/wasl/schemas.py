from datetime import date
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class TrackedField(BaseModel, Generic[T]):
    value: T | None = None
    status: Literal["known", "assumed", "missing"] = "missing"


class PastWork(BaseModel):
    title: str
    year: int
    role: str
    description: str
    collaborator_ids: list[str] = []


class Practitioner(BaseModel):
    id: str
    name: str
    type: Literal["individual", "company"]
    specialties: list[str]
    sectors: list[str]
    city: str
    remote_ok: bool
    price_min: int
    price_max: int
    availability: list[tuple[date, date]]
    past_works: list[PastWork]
    verified_license: bool
    is_rising_talent: bool
    is_demo: bool = True
    gender: Literal["male", "female"] | None = None  # None for companies / unknown
    # direct contact + affiliated company (for type="company" the company fields describe the entity itself)
    phone: str | None = None
    email: str | None = None
    company_name: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    company_website: str | None = None

    def contact(self) -> dict:
        return {"phone": self.phone, "email": self.email,
                "company": {"name": self.company_name, "phone": self.company_phone, "email": self.company_email,
                            "website": self.company_website} if self.company_name else None}

    @model_validator(mode="after")
    def _check(self):
        assert 0 < self.price_min <= self.price_max, "price range"
        assert all(s <= e for s, e in self.availability), "availability range"
        return self

    @property
    def collaborators(self) -> set[str]:
        return {c for w in self.past_works for c in w.collaborator_ids}


class Need(BaseModel):
    id: str
    role: str
    sector: str
    reason: str = ""
    consequence_if_ignored: str = ""
    importance: float = Field(0.5, ge=0, le=1)
    confidence: float = Field(0.5, ge=0, le=1)
    phase: str = ""
    phase_window: tuple[date, date]
    remote_ok: bool = False
    mentioned: bool = True


class ProjectCard(BaseModel):
    sector: TrackedField[str] = TrackedField()
    secondary_sectors: list[str] = []  # hybrid projects (e.g. fashion show with heritage roots)
    stage: TrackedField[str] = TrackedField()
    budget: TrackedField[int] = TrackedField()
    city: TrackedField[str] = TrackedField()
    start_date: TrackedField[date] = TrackedField()
    deadline: TrackedField[date] = TrackedField()
    show_date: TrackedField[date] = TrackedField()   # official show / launch day (تاريخ يوم العرض الرسمي)
    style: TrackedField[str] = TrackedField()        # desired work style / vibe (طابع العمل)
    needs: list[Need] = []


class ScoreBreakdown(BaseModel):
    specialty: float
    past_work_similarity: float
    location: float
    budget: float
    availability: float


class Candidate(BaseModel):
    practitioner_id: str
    need_id: str
    estimated_cost: int
    score: float
    score_breakdown: ScoreBreakdown
    is_available: bool
    location_match: bool


class OutOfScope(BaseModel):
    """An assignment outside the member's usual work scope (other city / remote-only vs on-site need).
    Allowed as a soft constraint: the member's fee carries a small symbolic surcharge."""
    reason: Literal["remote_preference", "outside_city"]
    member_city: str
    project_city: str | None = None
    base_cost: int
    surcharge: int
    note_ar: str
    note_en: str


class Team(BaseModel):
    assignments: dict[str, str]
    backups: dict[str, str]
    total_cost: int  # includes out-of-scope surcharges
    notes: list[str] = []
    out_of_scope: dict[str, OutOfScope] = {}  # need_id -> flag (only for soft-constraint assignments)

    def cost_of(self, need_id: str, base_cost: int) -> int:
        o = self.out_of_scope.get(need_id)
        return base_cost + (o.surcharge if o else 0)


class Concession(BaseModel):
    """One alternative minimal change that alone makes the problem feasible."""
    kind: Literal["extra_budget_sar", "shift_days", "allow_remote_needs"]
    value: int | list[str]
    detail: str = ""


class SolveResult(BaseModel):
    feasible: bool
    team: Team | None = None
    blocking_constraints: list[str] = []
    min_concessions: list[Concession] = []
