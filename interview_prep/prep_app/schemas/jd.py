from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class JDProfile:
    job_role: str
    company_name: str
    raw_text: str
    keywords: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.job_role or not self.company_name:
            raise ValueError("JDProfile requires job_role and company_name")
    
    def to_dict(self):
        return asdict(self)



