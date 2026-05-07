from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.templating import Jinja2Templates
from app import theme_cache
from app.utils import MOIS_LABELS, FREQ_LABELS, compliance_color, periode_label

templates = Jinja2Templates(directory="app/templates")

templates.env.globals["get_theme"] = theme_cache.get_theme
templates.env.globals["MOIS_LABELS"] = MOIS_LABELS
templates.env.globals["FREQ_LABELS"] = FREQ_LABELS
templates.env.globals["compliance_color"] = compliance_color
templates.env.globals["periode_label"] = periode_label
