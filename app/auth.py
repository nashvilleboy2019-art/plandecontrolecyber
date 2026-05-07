import bcrypt
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, AppConfig, ControlType, Category, Perimetre


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def get_config(db: Session, key: str, default=None):
    row = db.query(AppConfig).filter(AppConfig.key == key).first()
    return row.value if row else default


def ldap_authenticate(username: str, password: str, db: Session):
    if get_config(db, "ldap_enabled", "0") != "1":
        return None
    try:
        from ldap3 import Server, Connection, AUTO_BIND_NO_TLS, SUBTREE, Tls
        import ssl

        server_addr = get_config(db, "ldap_server", "")
        port = int(get_config(db, "ldap_port", "389"))
        domain = get_config(db, "ldap_domain", "")
        use_tls = get_config(db, "ldap_tls", "0") == "1"
        base_dn = get_config(db, "ldap_base_dn", "")
        allowed_ou = get_config(db, "ldap_allowed_ou", "")
        allowed_group = get_config(db, "ldap_allowed_group", "")
        default_role = get_config(db, "ldap_default_role", "auditeur")

        if not server_addr or not domain:
            return None

        if not base_dn:
            base_dn = "dc=" + ",dc=".join(domain.split("."))

        tls_config = Tls(validate=ssl.CERT_NONE) if use_tls else None
        server = Server(server_addr, port=port, tls=tls_config, get_info=None)
        user_dn = f"{username}@{domain}"
        conn = Connection(server, user=user_dn, password=password, auto_bind=True)

        if not conn.bound:
            return None

        # Fetch user attributes
        conn.search(
            base_dn,
            f"(sAMAccountName={username})",
            search_scope=SUBTREE,
            attributes=["distinguishedName", "memberOf", "mail", "displayName"]
        )

        if not conn.entries:
            return None

        entry = conn.entries[0]
        dn = str(entry.distinguishedName)

        if allowed_ou and allowed_ou.lower() not in dn.lower():
            return None

        if allowed_group:
            member_of = [str(g) for g in entry.memberOf] if entry.memberOf else []
            if not any(allowed_group.lower() in g.lower() for g in member_of):
                return None

        email = str(entry.mail) if entry.mail else None
        display_name = str(entry.displayName) if entry.displayName else username

        # Create or update local user
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                password_hash=hash_password(bcrypt.gensalt().decode()),
                role=default_role,
                email=email,
                nom_complet=display_name,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            if email:
                user.email = email
            if display_name:
                user.nom_complet = display_name
            db.commit()

        return user
    except Exception:
        return None


def authenticate(username: str, password: str, db: Session):
    # Try LDAP first
    user = ldap_authenticate(username, password, db)
    if user:
        return user

    # Local fallback
    user = db.query(User).filter(User.username == username, User.active == True).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def create_default_data():
    db = SessionLocal()
    try:
        # Default users
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(
                username="admin",
                password_hash=hash_password("erwanbogosse2026"),
                role="responsable",
                nom_complet="Administrateur",
            ))
        if not db.query(User).filter(User.username == "auditeur").first():
            db.add(User(
                username="auditeur",
                password_hash=hash_password("auditeur"),
                role="auditeur",
                nom_complet="Auditeur",
            ))

        # Default control types — only on first install (empty table)
        if db.query(ControlType).count() == 0:
            default_types = [
                ("Gestion des accès", "blue"),
                ("Surveillance et détection", "red"),
                ("Continuité et sauvegarde", "green"),
                ("Gestion des vulnérabilités", "orange"),
                ("Conformité et audit", "purple"),
            ]
            for i, (label, color) in enumerate(default_types):
                db.add(ControlType(label=label, color=color, ordre=i))

        # Default categories — only on first install
        if db.query(Category).count() == 0:
            for i, label in enumerate(["Entité A", "Entité B"]):
                db.add(Category(label=label, ordre=i))

        # Default perimetres — only on first install
        if db.query(Perimetre).count() == 0:
            for i, label in enumerate(["Périmètre SI", "Global"]):
                db.add(Perimetre(label=label, ordre=i))

        # Default app config
        defaults = {
            "company_name": "Plan de Contrôle Cyber",
            "theme_primary": "indigo",
            "theme_secondary": "slate",
            "logo_ext": "",
            "ldap_enabled": "0",
            "ldap_server": "",
            "ldap_port": "389",
            "ldap_domain": "",
            "ldap_tls": "0",
            "ldap_base_dn": "",
            "ldap_allowed_ou": "",
            "ldap_allowed_group": "",
            "ldap_default_role": "auditeur",
            "jira_enabled": "0",
            "jira_url": "",
            "jira_api_token": "",
            "jira_project_key": "",
            "jira_user_email": "",
            "alert_warning_days": "7",
            "alert_danger_days": "0",
        }
        for key, value in defaults.items():
            if not db.query(AppConfig).filter(AppConfig.key == key).first():
                db.add(AppConfig(key=key, value=value))

        db.commit()
    finally:
        db.close()
