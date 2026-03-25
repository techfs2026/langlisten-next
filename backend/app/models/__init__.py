# Import all models here so Alembic's autogenerate can detect them.
from app.models.material import AudioMaterial
from app.models.subtitle import Subtitle
from app.models.practice import PracticeSession, SentenceAttempt

__all__ = ["AudioMaterial", "Subtitle", "PracticeSession", "SentenceAttempt"]