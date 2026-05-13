from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="auditeur")  # auditeur | responsable
    email = Column(String(255))
    nom_complet = Column(String(255))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AppConfig(Base):
    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)


class ControlType(Base):
    __tablename__ = "control_types"
    id = Column(Integer, primary_key=True)
    label = Column(String(200), nullable=False)
    color = Column(String(50), default="blue")  # Tailwind color name
    ordre = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    controls = relationship("Control", back_populates="type")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    label = Column(String(100), nullable=False)
    description = Column(Text)
    ordre = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    controls = relationship("Control", back_populates="category")


class Perimetre(Base):
    __tablename__ = "perimetres"
    id = Column(Integer, primary_key=True)
    label = Column(String(100), nullable=False)
    description = Column(Text)
    ordre = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    controls = relationship("Control", back_populates="perimetre")


class Control(Base):
    __tablename__ = "controls"
    id = Column(Integer, primary_key=True)
    reference = Column(String(100), unique=True, nullable=False, index=True)
    libelle = Column(String(500), nullable=False)
    indicateur = Column(Text)  # What to measure
    objectif = Column(Text)    # How to verify
    frequence = Column(String(50), nullable=False)  # mensuel | bimestriel | trimestriel | semestriel | annuel
    type_id = Column(Integer, ForeignKey("control_types.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    perimetre_id = Column(Integer, ForeignKey("perimetres.id"))
    taux_cible = Column(Float, default=100.0)
    guide_url = Column(String(500))
    responsable_id = Column(Integer, ForeignKey("users.id"))
    archived = Column(Boolean, default=False)
    archived_at = Column(DateTime)
    archived_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    updated_by_id = Column(Integer, ForeignKey("users.id"))

    type = relationship("ControlType", back_populates="controls")
    category = relationship("Category", back_populates="controls")
    perimetre = relationship("Perimetre", back_populates="controls")
    responsable = relationship("User", foreign_keys=[responsable_id])
    results = relationship(
        "ControlResult", back_populates="control",
        order_by="desc(ControlResult.annee), desc(ControlResult.mois)"
    )
    history = relationship("ControlHistory", back_populates="control", order_by="desc(ControlHistory.changed_at)")
    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    plugin = relationship("ControlPlugin", back_populates="control", uselist=False)


class ControlResult(Base):
    __tablename__ = "control_results"
    __table_args__ = (
        UniqueConstraint("control_id", "annee", "mois", name="uq_control_period"),
    )
    id = Column(Integer, primary_key=True)
    control_id = Column(Integer, ForeignKey("controls.id"), nullable=False)
    annee = Column(Integer, nullable=False)
    mois = Column(Integer, nullable=False)  # month for mensuel; period index for others
    periode_label = Column(String(50))      # e.g. "Jan 2025", "T1 2025", "S1 2025", "2025"
    taux_conformite = Column(Float)         # 0–100, nullable means not yet entered
    statut = Column(String(50), default="en_attente")  # conforme | non_conforme | en_attente | na
    commentaire = Column(Text)
    jira_ticket = Column(String(200))
    incident_ref = Column(String(200))
    validated = Column(Boolean, default=False)
    validated_by_id = Column(Integer, ForeignKey("users.id"))
    validated_at = Column(DateTime)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    updated_by_id = Column(Integer, ForeignKey("users.id"))

    control = relationship("Control", back_populates="results")
    validated_by = relationship("User", foreign_keys=[validated_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    history = relationship("ResultHistory", back_populates="result", order_by="desc(ResultHistory.changed_at)")


class ControlHistory(Base):
    __tablename__ = "control_history"
    id = Column(Integer, primary_key=True)
    control_id = Column(Integer, ForeignKey("controls.id"), nullable=False)
    action = Column(String(100))   # created | updated | archived | restored
    changed_by_id = Column(Integer, ForeignKey("users.id"))
    changed_at = Column(DateTime, default=datetime.utcnow)
    old_values = Column(Text)      # JSON
    new_values = Column(Text)      # JSON
    note = Column(Text)

    control = relationship("Control", back_populates="history")
    changed_by = relationship("User")


class ResultHistory(Base):
    __tablename__ = "result_history"
    id = Column(Integer, primary_key=True)
    result_id = Column(Integer, ForeignKey("control_results.id"))
    control_id = Column(Integer, ForeignKey("controls.id"))
    action = Column(String(100))   # created | updated | validated | invalidated
    changed_by_id = Column(Integer, ForeignKey("users.id"))
    changed_at = Column(DateTime, default=datetime.utcnow)
    old_values = Column(Text)
    new_values = Column(Text)

    result = relationship("ControlResult", back_populates="history")
    control = relationship("Control")
    changed_by = relationship("User")


class ControlPlugin(Base):
    """Association d'un plugin d'automatisation à un contrôle (1 plugin max par contrôle)."""
    __tablename__ = "control_plugins"
    id = Column(Integer, primary_key=True, index=True)
    control_id = Column(Integer, ForeignKey("controls.id"), unique=True, nullable=False)
    plugin_slug = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    config_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    control = relationship("Control", back_populates="plugin")
    runs = relationship(
        "PluginRun", back_populates="control_plugin",
        order_by="desc(PluginRun.run_at)"
    )


class PluginRun(Base):
    """Résultat d'une exécution de plugin pour une période donnée."""
    __tablename__ = "plugin_runs"
    id = Column(Integer, primary_key=True, index=True)
    control_plugin_id = Column(Integer, ForeignKey("control_plugins.id"), nullable=False)
    annee = Column(Integer, nullable=False)
    mois = Column(Integer, nullable=False)
    plugin_slug = Column(String(100), nullable=False)
    control_date = Column(String(10))        # YYYY-MM-DD
    status = Column(String(20), default="done")  # done | validated
    result_json_path = Column(String(255), nullable=True)
    excel_path = Column(String(255), nullable=True)
    taux_conformite = Column(Float, nullable=True)
    commentaire_auto = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    run_at = Column(DateTime, default=datetime.utcnow)
    run_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime, nullable=True)
    validated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    control_plugin = relationship("ControlPlugin", back_populates="runs")
    run_by = relationship("User", foreign_keys=[run_by_id])
    validated_by = relationship("User", foreign_keys=[validated_by_id])


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String(100))
    action = Column(String(200))
    resource = Column(String(100))
    resource_id = Column(Integer)
    details = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
