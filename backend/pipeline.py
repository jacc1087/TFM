"""
pipeline.py — Script de procesado de datos para el TFM de restaurantes de Madrid.

Consolida en un único archivo todos los scripts de preprocesado:
  · analizar_todos_restaurantes.py  → análisis NLP + extracción de platos
  · fix_cocina.py                   → detección de cocina y categoría de carta
  · regenerar_criterios.py          → recálculo de criterios cualitativos
  · regenerar_frases.py             → regeneración de frases con Gemini
  · actualizar_personal_destacado.py→ actualización del personal destacado
  · generar_geo.py                  → geocodificación de direcciones

Uso:
    python pipeline.py                      # Ejecuta el pipeline completo
    python pipeline.py --solo-criterios     # Solo recalcula criterios
    python pipeline.py --solo-personal      # Solo actualiza personal destacado
    python pipeline.py --solo-frases        # Solo regenera frases (Gemini)
    python pipeline.py --solo-cocina        # Solo detecta cocina y categoría
    python pipeline.py --solo-geo           # Solo geocodifica direcciones

Archivos necesarios en el mismo directorio:
    resenas_unificadas.csv          → reseñas de Google Maps
    ranking.csv                     → ranking con Valoracion, Votaciones, Dirección
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

import os
import re
import sys
import json as _json
import math
import time as _time
import unicodedata
import warnings
import urllib.request as _ureq
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import pipeline as hf_pipeline
import nltk
from nltk.corpus import stopwords

warnings.filterwarnings('ignore')

nltk.download('punkt',     quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))

# Rutas de archivos de entrada y salida
CSV_RESENAS     = os.path.join(BASE_DIR, "resenas_unificadas.csv")
CSV_RANKING     = os.path.join(BASE_DIR, "ranking.csv")
OUTPUT_CSV      = os.path.join(BASE_DIR, "analisis_restaurantes.csv")
OUTPUT_RESENAS  = os.path.join(BASE_DIR, "analisis_restaurantes_resenas.csv")
OUTPUT_GEO      = os.path.join(BASE_DIR, "restaurantes_geo.csv")

# Rutas de caché (se generan automáticamente en ejecuciones previas)
CACHE_PLATOS    = os.path.join(BASE_DIR, ".cache_platos_gemini.json")
CACHE_NORM      = os.path.join(BASE_DIR, ".cache_norm_gemini.json")
CACHE_CRITERIOS = os.path.join(BASE_DIR, ".cache_criterios_gemini.json")
CACHE_NOMBRES   = os.path.join(BASE_DIR, ".cache_nombres_gemini.json")
CACHE_COORDS    = os.path.join(BASE_DIR, ".cache_coords.json")

# Parámetros del modelo NLP
MODELO_HF       = "nlptown/bert-base-multilingual-uncased-sentiment"
BATCH_SIZE      = 32
MIN_MENCIONES   = 10
MIN_CONFIANZA   = 0.50

# Modelo Gemini
GEMINI_MODEL    = "gemini-2.5-flash"

# Modo económico: desactiva normalización y extracción de personal para ahorrar tokens
MODO_ECONOMICO  = False

# ── Cargar variables de entorno desde .env si existe ─────────────────────────
_env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

# ═══════════════════════════════════════════════════════════════════════════════
# VOCABULARIO: STOPWORDS Y LISTAS DE PLATOS
# ═══════════════════════════════════════════════════════════════════════════════

STOP_ES = set(stopwords.words('spanish')) | {
    'si','así','tan','ser','año','vez','bien','muy','más','menos',
    'todo','toda','todos','cada','este','esta','estos','estas',
    'aún','ahí','allí','aquí','hay','era','fue','han','has',
    'hemos','nos','les','lo','la','las','los','del','al',
    'un','una','unos','unas','su','sus','mi','mis','se','me',
    'te','le','que','de','en','y','a','el','es','por','con',
    'para','como','no','pero','o','si','cuando','donde','aunque',
}

# Palabras que no son nombres de platos (se usan para filtrar candidatos)
NO_PLATOS = {
    'restaurante','comida','cocina','servicio','trato','atención','experiencia','lugar',
    'sitio','personal','camarero','camarera','ambiente','precio','calidad','carta',
    'mesa','plato','platos','producto','productos','local','establecimiento',
    'buena','bueno','buen','buenos','buenas','rico','rica','ricos','ricas',
    'riquísimo','delicioso','deliciosa','deliciosos','deliciosas',
    'exquisito','exquisita','espectacular','increíble','perfecto','perfecta',
    'impecable','excepcional','excelente','fantástico','fantástica',
    'maravilloso','maravillosa','inmejorable','estupendo','estupenda',
    'sobresaliente','alucinante','brutal','genial','fenomenal',
    'recomendable','insuperable','único','única','especial','auténtico',
    'fresco','fresca','sabroso','sabrosa','increible','magnifico',
    'deliciosa','mejor','peor','igual','mismo','misma',
    'rapido','rapida','amable','amables','atento','atenta','atentos','atentas',
    'agradable','agradables','simpatico','simpatica','profesional','profesionales',
    'gracias','encantado','encantada','satisfecho','satisfecha',
    'volver','volveremos','volvería','repetiremos','repetir',
    'recomiendo','recomendamos','recomendable','recomendado','recomendada',
    'pedimos','pedí','tomamos','probamos','atendió','atendieron',
    'reserva','mesa','cuenta','nota','propina',
    'madrid','barcelona','españa','galicia','india','italia','japón',
    'familia','amigos','pareja','grupo','equipo','compañeros',
    'menú','degustación','carta','precios','euros','coste',
    'calidad precio','buena relacion',
}

# Palabras que NUNCA deben aparecer en un nombre de plato
NEGACIONES = {'no','sin','nunca','tampoco','ni','jamás','jamas','nada'}

ADJETIVOS_INICIO = {
    'buena','bueno','buenos','buenas','gran','grande','grandes',
    'muy','mejor','peor','rica','rico','ricos','ricas',
    'excelente','excelentes','increíble','increíbles','espectacular',
    'fantástico','fantástica','maravilloso','maravillosa','perfecto','perfecta',
    'impecable','excepcional','deliciosa','delicioso','sabroso','sabrosa',
    'calidad','precio','buen','súper','super',
    'servicio','camarero','camarera','lugar','ambiente','trato',
    'comida','cocina',
}

PATRONES_NO_PLATO = re.compile(
    r'^(muy|gran|super|súper|bien|mal|sin|con|para|como|desde|hasta|'
    r'nuestro|nuestra|todo|toda|todos|todas|'
    r'primer|primera|segundo|segunda|otro|otra|cada|mismo|misma)$'
    r'|'
    r'(mente|ísimo|ísima|ísimos|ísimas|ción|sión)$'
)

# Lista blanca de platos conocidos (se detectan directamente aunque no sean bigramas)
PLATOS_WHITELIST = {
    'pulpo','chuletón','chuleton','cochinillo','lechazo','cordero','rabo','carrillera',
    'bacalao','merluza','rodaballo','lubina','dorada','rape','salmón','salmon',
    'atún','atun','bonito','anchoas','gambas','langostinos','calamares','chipirones',
    'mejillones','almejas','berberechos','navajas','percebes','langosta','bogavante',
    'sepia','cocochas',
    'cachopo','cachopos','fabada','callos','kokotxas','marmitako',
    'pimientos rellenos','pisto manchego','migas','gazpacho manchego',
    'papas arrugadas','mojo','escudella','porrusalda','txangurro','angulas',
    'secreto ibérico','secreto','presa ibérica','presa','pluma ibérica','pluma',
    'carrillada','oreja','manitas','callos a la madrileña',
    'albóndigas','albondigas','rabo de toro','rabo toro',
    'jamón','jamon','lomo','chorizo','morcilla','salchichón','salchicon','sobrasada',
    'cecina','foie','mollejas',
    'paella','arroz','risotto','fideuá','fideua','pasta','espaguetis','lasaña','lasana',
    'carbonara','penne','ravioli','tagliatelle',
    'croquetas','croqueta','patatas bravas','tortilla','gazpacho','salmorejo',
    'ensaladilla','berenjenas','pimientos','pisto','ratatouille','hummus',
    'guacamole','nachos','bruschetta','focaccia','tostas',
    'tikka masala','biryani','naan','samosa','curry','korma','dal','tandoori',
    'arepas','arepa','pabellón','pabellon','cachapas','tequeños','tequenos',
    'empanadas','empanada','ceviche','tiradito','lomo saltado','causa','anticuchos',
    'sushi','sashimi','ramen','gyozas','edamame','tempura','miso',
    'tacos','burrito','quesadilla','fajitas',
    'tarta','tartaleta','coulant','brownie','tiramisú','tiramisu','panna cotta',
    'flan','crema catalana','helado','mousse','cheesecake','mochi',
    'churros','soufflé','souffle','crepe','waffle',
    'sangría','sangria','mojito','margarita','caipirinha','negroni','martini',
    # Platos asturianos
    'cachopo','cachopu','fabada asturiana','fabada','pote asturiano','oricios',
    'tortos','torto','frixuelos','verdinas','compango','cabrales',
    # Platos vascos
    'pintxos','pintxo','gilda','pil pil',
    # Platos madrileños
    'cocido madrileño','cocido madrileno','cocido','cocido completo',
    'callos madrilenos','huevos rotos','huevos estrellados',
    'bocadillo de calamares','soldaditos de pavía',
    # Postres
    'arroz con leche','leche frita','bizcocho','torrijas',
    # Cortes de carne
    'chuletón de buey','entrecot','solomillo','filete','entraña','costillar',
    # Mariscos adicionales
    'zamburiñas','nécoras','centollo','buey de mar',
    'boquerones','gambas al ajillo','carabineros','cigalas','ostras',
    # Bebidas
    'vermut','vermu','vermú','txakoli','sidra',
}

# Lista negra de falsos positivos — se rechazan siempre con prioridad absoluta
PLATOS_BLACKLIST = {
    'siempre la comida','la comida siempre','toda la comida','muy buena comida',
    'buenísima comida','la mejor comida','toda la carta','todo muy bueno',
    'todo estuvo','todo estaba','todo rico','todo bueno','todo excelente',
    'siempre bueno','siempre bien','muy recomendable','muy bien todo',
    'primera vez','segunda vez','primera visita','próxima visita',
    'muy buen servicio','buen servicio','gran servicio',
    'muy buen trato','muy buena atención',
    'verdad que sushi','sushi más divino','sushi de calidad','sushi de madrid',
    'local muy bonito','local bonito','bonito y limpio','sitio bonito',
    'pasta y la pizza','pasta como la pizza','pasta y pizza',
    'pedimos nachos','pedimos arroz','pedimos croquetas',
    'pedimos unas gyozas','pedimos una pasta','pedí una paella',
    'probamos arroz','probamos unos tagliatelle',
    'postre la tarta','postre tarta','postre torrijas','postre helado',
    'cordero excepcional','cordero espectacular',
    'sashimi espectacular','arroz muy bueno','pasta muy buena',
    'tiramisú y el helado','boloñesa el tiramisú',
}

# ═══════════════════════════════════════════════════════════════════════════════
# VOCABULARIO: CRITERIOS Y DIMENSIONES
# ═══════════════════════════════════════════════════════════════════════════════

# Keywords que señalan la presencia de cada criterio cualitativo en una reseña
CRITERIOS_SIGNAL = {
    'ninos':               ['niño','niños','niña','niñas','bebé','bebe','infantil',
                            'sillita','trona','peques','pequeños','crío','crios','chaval'],
    'mascotas':            ['perro','perros','mascota','mascotas','peludo','peludos',
                            'admiten perros','dog','pet'],
    'terraza':             ['terraza','terrazas','exterior','al aire libre',
                            'patio','veladores','parasol'],
    'vistas':              ['vistas','panorámica','panoramica','azotea','rooftop',
                            'mirador','skyline','horizonte'],
    'musica_directo':      ['música en directo','música directo','concierto',
                            'actuación','actuacion','banda','grupo en vivo','en vivo',
                            'jazz','flamenco en directo'],
    'romantico':           ['romántico','romantico','romántica','romantica',
                            'íntimo','intimo','íntima','intima',
                            'cena romántica','velas'],
    'buen_postre':         ['postre','postres','tarta','helado','tiramisú','tiramisu',
                            'mousse','coulant','brownie','cheesecake','flan',
                            'crema catalana','panna cotta'],
    'precio_calidad':      ['calidad precio','calidad-precio','relacion calidad',
                            'relación calidad','precio razonable','precio asequible',
                            'muy economico','muy económico','precio justo',
                            'buena relacion','buena relación'],
    'grupos_grandes':      ['grupo grande','grupos grandes','celebracion','celebración',
                            'cumpleanos','cumpleaños','evento privado','reserva para grupo',
                            'cena de empresa','comida de empresa','gran grupo'],
    'vegano_vegetariano':  ['vegano','vegana','vegetariano','vegetariana',
                            'opciones veganas','opciones vegetarianas',
                            'plant based','sin carne','menú vegano'],
    'sin_gluten':          ['sin gluten','celiaco','celiaca','celíaco','celíaca',
                            'gluten free','opcion sin gluten','opción sin gluten'],
}

# Descripción de cada criterio para usar en los prompts de Gemini
CRITERIOS_DESC = {
    'ninos':               'apto para niños o familias con bebés/niños pequeños',
    'mascotas':            'admite mascotas o perros',
    'terraza':             'tiene terraza o espacio exterior disponible',
    'vistas':              'tiene vistas panorámicas, azotea o mirador',
    'musica_directo':      'ofrece música en directo, conciertos o actuaciones',
    'romantico':           'ambiente romántico o íntimo',
    'buen_postre':         'destacan los postres según los clientes',
    'precio_calidad':      'buena relación calidad-precio mencionada explícitamente',
    'grupos_grandes':      'apto para grupos grandes, celebraciones o eventos',
    'vegano_vegetariano':  'tiene opciones veganas o vegetarianas claras',
    'sin_gluten':          'tiene opciones sin gluten o apto para celíacos',
}

# Mínimo de menciones para considerar un criterio como activo (sin Gemini)
MIN_MENCIONES_CRITERIOS = {
    'ninos': 3, 'mascotas': 2, 'terraza': 3, 'vistas': 3,
    'musica_directo': 2, 'romantico': 3, 'buen_postre': 4,
    'precio_calidad': 4, 'grupos_grandes': 3, 'vegano_vegetariano': 2, 'sin_gluten': 2,
}

# Keywords para cada dimensión de análisis estadístico
DIMENSIONES_KEYWORDS = {
    'servicio':       ['servicio','camarero','camarera','atención','atento','amable',
                       'profesional','trato','pendiente','recomendó','recomendaron'],
    'comida':         ['comida','plato','carta','sabor','calidad','producto','fresco',
                       'rico','riquísimo','delicioso','exquisito'],
    'ambiente':       ['ambiente','local','decoración','acogedor','elegante','bonito',
                       'atmósfera','espacio','tranquilo','íntimo'],
    'precio':         ['precio','caro','barato','relación','calidad-precio','coste','euros'],
    'velocidad':      ['rápido','lento','espera','tardó','tiempo','prisas','ágil'],
    'ruido':          ['ruido','ruidoso','silencioso','tranquilo','música'],
    'limpieza':       ['limpio','limpieza','higiene','aseado'],
    'ninos':          ['niño','niños','niña','niñas','bebé','familiar','infantil','sillita','trona'],
    'mascotas':       ['perro','perros','mascota','mascotas','peludo','admiten perros','dog','pet'],
    'terraza':        ['terraza','terrazas','exterior','exteriores','al aire libre',
                       'fuera','jardín','patio','veladores'],
    'vistas':         ['vistas','vista','panorámica','panoramica','azotea','rooftop','mirador'],
    'musica_directo': ['música en directo','música directo','directo','concierto',
                       'actuación','banda','jazz','flamenco en directo'],
    'romantico':      ['romántico','romantico','íntimo','intimo','pareja',
                       'cena romántica','velas','aniversario'],
}

# ═══════════════════════════════════════════════════════════════════════════════
# VOCABULARIO: DETECCIÓN DE COCINA
# ═══════════════════════════════════════════════════════════════════════════════

# Platos representativos de cada cocina para detectarla por los platos del restaurante
PLATOS_POR_COCINA = {
    'gallega':    ['empanada gallega','percebes','vieiras','caldo gallego','lacon','filloas','zorza'],
    'asturiana':  ['cachopo','cachopu','fabada asturiana','fabada','oricios','cabrales','tortos','verdinas'],
    'vasca':      ['pintxos','pintxo','gilda','kokotxas','cocochas','txangurro','marmitako','pil pil','angulas'],
    'andaluza':   ['pescaito frito','tortillitas de camarones','ajoblanco','berenjenas con miel','cola de toro'],
    'madrileña':  ['cocido madrileño','cocido madrileno','callos a la madrileña','bocadillo de calamares'],
    'italiana':   ['carbonara','cacio e pepe','amatriciana','ossobuco','panna cotta','tiramisú','tiramisu',
                   'tagliatelle','pappardelle','gnocchi','cannoli','arancini','burrata','lasaña','pizza'],
    'peruana':    ['lomo saltado','lomo salteado','causa','causa limeña','anticuchos','aji de gallina',
                   'leche de tigre','chaufa','tiradito'],
    'japonesa':   ['ramen','sushi','sashimi','nigiri','gyozas','gyoza','tempura','udon','mochi','yakitori'],
    'india':      ['tikka masala','biryani','naan','samosa','korma','dal','tandoori','butter chicken'],
    'mexicana':   ['tacos','burrito','quesadilla','fajitas','enchilada','pozole','carnitas','tamales'],
    'venezolana': ['arepa','arepas','pabellon','cachapa','hallaca','tequeños','mandocas','caraotas'],
    'argentina':  ['entraña','mollejas','chorizo criollo','empanadas argentinas','lomo alto','chimichurri'],
    'arabe':      ['shawarma','falafel','tabule','baba ganoush','labneh','shakshuka','couscous'],
    'americana':  ['smash burger','pulled pork','costillas bbq','mac and cheese','chicken wings','brisket'],
    'griega':     ['gyros','souvlaki','moussaka','spanakopita','baklava','dolmades'],
    'china':      ['dim sum','wonton','pato pekin','chow mein','dumplings'],
    'tailandesa': ['pad thai','tom yum','massaman','satay'],
    'francesa':   ['foie gras','confit de pato','magret','bouillabaisse','escargots','cassoulet'],
    'colombiana': ['bandeja paisa','ajiaco','sancocho'],
}

# Keywords del nombre del restaurante para detectar cocina directamente
NOMBRE_KEYWORDS_COCINA = {
    'gallega':    ['galicia','gallego','gallega'],
    'asturiana':  ['asturian','asturias'],
    'vasca':      ['txirimiri','dantxari','txoko','euskal'],
    'andaluza':   ['gaditana','gaditano','sevill','andaluz'],
    'madrileña':  ['madril'],
    'argentina':  ['argentin','pampa beef','cabaña argentina','bayres','asado central','camoati'],
    'italiana':   ['trattoria','pizzeria','pizzart','mozzarell','napoli','piamonte',
                   'fusco','pastamore','malafemmena','malatesta','pulcinella',
                   'maruzzella','oliveto','piccola','davanti'],
    'japonesa':   ['sibuya','hotaru','miyama','ichikani','dokidoki','kaiten sushi','sr.ito','sakale'],
    'india':      ['indian','tandoori','bangalore','kathmandu','purnima',
                   'radhuni','curry masala','indian aroma'],
    'mexicana':   ['taco bar','mawey','el rey de los tacos','tacos &'],
    'peruana':    ['kausa','quispe','tampu','ronda 14'],
    'venezolana': ['grama lounge'],
    'arabe':      ['hummuseria','beytna'],
    'americana':  ['steakburger','steak burger','hamburgues','burnout','brew wild'],
    'fusion':     ['diverxo','streetxo','dstage','bacira','coque','bestial','casa jaguar'],
}

# Platos por categoría de carta (asador, marisquería, arrocería…)
PLATOS_CATEGORIA = {
    'asador':         ['chuleton','chuletón','lechazo','entraña','lomo alto','costillar','cordero asado'],
    'marisqueria':    ['percebes','vieiras','navajas','ostras','cigalas','bogavante',
                       'langosta','carabineros','centollo','buey de mar'],
    'arroceria':      ['paella valenciana','arroz negro','arroz con bogavante',
                       'fideuá','fideua','paella de marisco','paella mixta','arroz meloso'],
    'japones':        ['sushi','ramen','sashimi','gyozas','gyoza','tempura','udon','mochi','nigiri'],
    'italiano':       ['carbonara','tiramisú','tiramisu','tagliatelle','pappardelle',
                       'gnocchi','lasaña','pizza','bruschetta','panna cotta'],
    'indio':          ['tikka masala','biryani','naan','samosa','korma','tandoori','butter chicken'],
    'mexicano':       ['tacos','quesadilla','burrito','fajitas','enchilada','pozole'],
    'peruano':        ['lomo saltado','lomo salteado','causa','tiradito','anticuchos','aji de gallina'],
    'venezolano':     ['arepa','arepas','pabellon','cachapa','tequeños','hallaca'],
    'argentino':      ['entraña','mollejas','chorizo criollo','empanadas argentinas','lomo alto','chimichurri'],
    'tailandes':      ['pad thai','tom yum','massaman','curry panang','satay'],
    'arabe':          ['shawarma','falafel','hummus','tabule','shakshuka','baba ganoush','couscous'],
    'hamburgueseria': ['smash burger','pulled pork','costillas bbq','mac and cheese','chicken wings'],
}

# Palabras que NUNCA son nombres de persona (para filtrar personal destacado)
STOP_PERSONAL = {
    'el','la','los','las','un','una','de','del','al','en','con','por','que',
    'nos','les','fue','es','era','son','muy','todo','bien','mal','hay','han',
    'comida','servicio','lugar','sitio','restaurante','mesa','plato','trato',
    'precio','ambiente','terraza','carta','vino','agua','pan','cafe','postre',
    'excelente','bueno','buena','malo','mala','genial','increible','perfecto',
    'impecable','fantastico','amable','atento','atenta','profesional','maravilloso',
    'siempre','nunca','tambien','ademas','mucho','poco','nada','algo',
    'personal','equipo','staff','gente','chico','chica','senor','senora',
    'madrid','calle','verdad','parte','lado','vez','veces','dia','noche',
    'tarde','atencion','experiencia','visita','reserva','rapido',
    'recomendable','recomendado','volveremos','volvere','volveria','repetir',
    'camarero','camarera','chef','cocinero','maitre','gerente','encargado',
    'dueno','duena','propietario','socio','sala','cocina','local','negocio',
}

# Patrones de mención directa de nombres de personal en reseñas
PATRONES_PERSONAL = [
    r'gracias\s+a\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12})(?:\s+y\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12}))?',
    r'de\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12})\s+(?:fue|estuvo)\s+(?:excelente|impecable|genial|fantastico|perfecto|excepcional)',
    r'([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12})\s+(?:fue|es|estuvo)\s+(?:muy\s+|super\s+)?(?:amable|atento|atenta|profesional|genial|impecable|simpatico|encantador)',
    r'(?:el\s+camarero|la\s+camarera|el\s+chef|el\s+maitre|el\s+encargado|la\s+encargada)\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12})',
    r'nos\s+(?:atendio|ayudo|explico|recomendo|asesoro|recibio)\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12})',
    r'(?:destacar|mencionar|agradecer|felicitar)\s+a\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12})',
    r'atendidos?\s+por\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12})',
    r'(?:labor|trabajo|profesionalidad|dedicacion|amabilidad)\s+de\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]{3,12})',
]

# ═══════════════════════════════════════════════════════════════════════════════
# CACHÉ EN MEMORIA
# ═══════════════════════════════════════════════════════════════════════════════

_cache_es_plato:      dict = {}  # término → True/False (Gemini clasificó como plato)
_cache_normalizacion: dict = {}  # lista de platos → lista normalizada
_cache_criterios:     dict = {}  # id_restaurante → dict de criterios
_cache_nombres:       dict = {}  # término → True/False (Gemini clasificó como nombre de persona)

# Contadores de tokens para estimar el coste de Gemini
_tok_input  = 0
_tok_output = 0


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE CACHÉ
# ═══════════════════════════════════════════════════════════════════════════════

def cargar_cache():
    """Carga todos los archivos de caché desde disco al inicio del pipeline."""
    global _cache_es_plato, _cache_normalizacion, _cache_criterios, _cache_nombres

    if os.path.exists(CACHE_PLATOS):
        try:
            with open(CACHE_PLATOS, 'r', encoding='utf-8') as f:
                loaded = _json.load(f)
            # Solo conservar los True; los False se reevalúan si hay blacklist nueva
            _cache_es_plato = {k: v for k, v in loaded.items()
                               if v is True and k not in PLATOS_BLACKLIST}
            print(f"Cache platos:        {len(_cache_es_plato)} aprobados.")
        except Exception:
            _cache_es_plato = {}

    if os.path.exists(CACHE_NORM):
        try:
            with open(CACHE_NORM, 'r', encoding='utf-8') as f:
                _cache_normalizacion = _json.load(f)
            print(f"Cache normalización: {len(_cache_normalizacion)} conjuntos.")
        except Exception:
            _cache_normalizacion = {}

    if os.path.exists(CACHE_CRITERIOS):
        try:
            with open(CACHE_CRITERIOS, 'r', encoding='utf-8') as f:
                _cache_criterios = _json.load(f)
            print(f"Cache criterios:     {len(_cache_criterios)} restaurantes.")
        except Exception:
            _cache_criterios = {}

    if os.path.exists(CACHE_NOMBRES):
        try:
            with open(CACHE_NOMBRES, 'r', encoding='utf-8') as f:
                _cache_nombres.update(_json.load(f))
            print(f"Cache nombres:       {len(_cache_nombres)} términos.")
        except Exception:
            pass


def guardar_cache():
    """Persiste todos los cachés en disco."""
    try:
        with open(CACHE_PLATOS, 'w', encoding='utf-8') as f:
            _json.dump(_cache_es_plato, f, ensure_ascii=False, indent=2)
        with open(CACHE_NORM, 'w', encoding='utf-8') as f:
            _json.dump(_cache_normalizacion, f, ensure_ascii=False, indent=2)
        with open(CACHE_CRITERIOS, 'w', encoding='utf-8') as f:
            _json.dump(_cache_criterios, f, ensure_ascii=False, indent=2)
        with open(CACHE_NOMBRES, 'w', encoding='utf-8') as f:
            _json.dump(_cache_nombres, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️  No se pudo guardar caché: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES DE TEXTO
# ═══════════════════════════════════════════════════════════════════════════════

def normalizar_texto(texto) -> str:
    """Convierte a minúsculas, elimina acentos y normaliza espacios."""
    s = str(texto).lower().strip()
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def limpiar(texto) -> str:
    """Normaliza texto eliminando caracteres no alfabéticos para comparaciones."""
    if not isinstance(texto, str):
        texto = '' if texto is None or (isinstance(texto, float) and np.isnan(texto)) else str(texto)
    texto = texto.lower()
    texto = re.sub(r'[^a-záéíóúüñ\s]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def estrellas_a_categoria(e: int) -> str:
    """Convierte número de estrellas (1-5) en categoría de sentimiento."""
    if e >= 4: return 'positivo'
    if e == 3: return 'neutro'
    return 'negativo'


def tiene_negacion(texto: str, keyword: str, ventana: int = 25) -> bool:
    """Comprueba si el keyword está precedido por una negación en el texto."""
    idx = texto.find(keyword)
    if idx == -1:
        return False
    contexto = texto[max(0, idx - ventana):idx]
    return any(neg in contexto for neg in {'no ', 'sin ', 'nunca ', 'tampoco ', 'ni ', 'nada '})


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE GEMINI
# ═══════════════════════════════════════════════════════════════════════════════

def _registrar_uso(prompt_chars: int, output_chars: int):
    """Acumula tokens estimados (1 token ≈ 4 chars) para el cálculo de coste."""
    global _tok_input, _tok_output
    _tok_input  += prompt_chars  // 4
    _tok_output += output_chars  // 4


def coste_estimado() -> float:
    """Devuelve el coste acumulado estimado en EUR (gemini-2.5-flash, junio 2025)."""
    usd = (_tok_input / 1_000_000 * 0.075) + (_tok_output / 1_000_000 * 0.30)
    return usd * 0.92


def _gemini_call(url: str, data: bytes, retries: int = 4) -> str:
    """Realiza una llamada HTTP a la API de Gemini con reintentos ante errores 429/503."""
    for intento in range(retries):
        try:
            req  = _ureq.Request(url, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
            resp = _ureq.urlopen(req, timeout=20)
            result = _json.loads(resp.read())
            texto  = ""
            for part in result["candidates"][0]["content"]["parts"]:
                if part.get("text", "").strip():
                    texto = part["text"].strip()
            _registrar_uso(len(data), len(texto))
            return texto
        except Exception as e:
            if any(c in str(e) for c in ['503', '429', '500']) and intento < retries - 1:
                espera = 2 ** (intento + 1)
                print(f"      [Gemini] reintentando en {espera}s...")
                _time.sleep(espera)
            else:
                return ""
    return ""


def gemini_json(prompt: str, max_tokens: int = 200) -> dict:
    """Llama a Gemini esperando una respuesta en JSON. Devuelve dict vacío en caso de fallo."""
    if not GEMINI_KEY:
        return {}
    data = _json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    texto = _gemini_call(url, data)
    _time.sleep(0.5)
    if not texto:
        return {}
    texto = texto.replace("```json", "").replace("```", "").strip()
    inicio = texto.find("{"); fin = texto.rfind("}") + 1
    if inicio >= 0 and fin > inicio:
        texto = texto[inicio:fin]
    try:
        return _json.loads(texto)
    except Exception:
        return {}


def gemini_texto(prompt: str, max_tokens: int = 150) -> str:
    """Llama a Gemini esperando texto libre. Ahorra tokens con prompts compactos."""
    if not GEMINI_KEY:
        return ""
    data = _json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": max_tokens},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    texto = _gemini_call(url, data)
    _time.sleep(0.3)
    return texto.strip()


def parafrasear_frases(fragmentos: list, contexto: str = "") -> str:
    """
    Recibe fragmentos literales de reseñas y devuelve 1-2 frases parafraseadas.
    No reproduce texto literal ni identifica a personas. Coste: ~80 tokens.
    """
    if not fragmentos or not GEMINI_KEY:
        return ""
    frags_txt = " | ".join(f[:120] for f in fragmentos[:3])
    prompt = (
        f"Reescribe en 1-2 frases naturales y limpias lo que expresan estas opiniones "
        f"de clientes sobre {contexto}. Sin comillas, sin nombres propios, "
        f"sin reproducir el texto original. Solo la idea principal.\n"
        f"Opiniones: {frags_txt}\nFrases:"
    )
    return gemini_texto(prompt, max_tokens=80)


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE PLATOS
# ═══════════════════════════════════════════════════════════════════════════════

def _dedup_local(platos: list) -> list:
    """Fusiona variantes locales del mismo plato (ej: 'croqueta' y 'croquetas')."""
    resultado = {}
    for nombre, cuenta in sorted(platos, key=lambda x: -x[1]):
        ya = False
        for clave in list(resultado.keys()):
            if (nombre in clave or clave in nombre) and abs(len(nombre) - len(clave)) <= 3:
                resultado[clave] += cuenta
                ya = True
                break
        if not ya:
            resultado[nombre] = resultado.get(nombre, 0) + cuenta
    return sorted(resultado.items(), key=lambda x: -x[1])


def filtrar_platos_con_gemini(candidatos: list, nombre_restaurante: str = "") -> list:
    """
    Filtra candidatos a nombre de plato usando whitelist/blacklist locales y,
    para los dudosos, una única llamada a Gemini con todos ellos a la vez.
    """
    resultado = []
    por_consultar = []

    for nombre, cuenta in candidatos:
        # Blacklist tiene prioridad absoluta
        if nombre in PLATOS_BLACKLIST:
            _cache_es_plato[nombre] = False
            continue
        # Si está en whitelist, aprobar directamente
        if nombre in PLATOS_WHITELIST or any(
            nombre == wl or nombre.startswith(wl + ' ') or nombre.endswith(' ' + wl)
            for wl in PLATOS_WHITELIST
        ):
            resultado.append((nombre, cuenta))
        elif nombre in _cache_es_plato:
            if _cache_es_plato[nombre]:
                resultado.append((nombre, cuenta))
        else:
            por_consultar.append((nombre, cuenta))

    if not por_consultar:
        return resultado

    # Sin Gemini: usar heurística basada en patrones
    if not GEMINI_KEY:
        for nombre, cuenta in por_consultar:
            if PATRONES_NO_PLATO.search(nombre):
                _cache_es_plato[nombre] = False
            else:
                _cache_es_plato[nombre] = True
                resultado.append((nombre, cuenta))
        return resultado

    # Con Gemini: clasificar todos los dudosos en una sola llamada
    nombres_consultar = [n for n, _ in por_consultar]
    prompt = (
        f"Clasifica estos candidatos a NOMBRE DE PLATO: {nombres_consultar}\n"
        "es_plato → nombre concreto de un plato, bebida o ingrediente.\n"
        "no_es_plato → frases con verbos, adjetivos valorativos o descripciones genéricas.\n"
        "REGLA: si contiene verbo o adjetivo valorativo → no_es_plato SIN EXCEPCIÓN.\n"
        'JSON SOLO: {"es_plato":[...],"no_es_plato":[...]}'
    )
    parsed = gemini_json(prompt, max_tokens=250)
    aprobados = set(parsed.get("es_plato", []))

    for nombre, cuenta in por_consultar:
        if nombre in aprobados:
            _cache_es_plato[nombre] = True
            resultado.append((nombre, cuenta))
        else:
            _cache_es_plato[nombre] = False

    return resultado


def normalizar_platos(platos: list) -> list:
    """
    Corrige ortografía y fusiona variantes del mismo plato usando Gemini.
    Usa caché para evitar llamadas repetidas con los mismos platos.
    """
    if not platos:
        return platos

    # Fusionar duplicados locales antes de llamar a Gemini
    vistos: dict = {}
    for nombre, cuenta in platos:
        vistos[nombre] = vistos.get(nombre, 0) + cuenta
    platos = sorted(vistos.items(), key=lambda x: -x[1])

    if not GEMINI_KEY:
        return platos

    nombres    = [t for t, _ in platos]
    cache_key  = '|'.join(nombres)

    if cache_key in _cache_normalizacion:
        corregidos = _cache_normalizacion[cache_key]
    else:
        prompt = (
            f"Normaliza estos nombres de platos: {nombres}\n"
            "- Corrige ortografía y acentos (nan→naan, bunuelos→buñuelos)\n"
            "- Fusiona variantes del MISMO plato con el nombre canónico\n"
            "- Minúsculas, no traduzcas\n"
            "- Devuelve exactamente el mismo número de elementos en el mismo orden\n"
            'Responde SOLO con: {"nombres": ["nombre1", "nombre2"]}'
        )
        parsed     = gemini_json(prompt, max_tokens=120)
        corregidos = parsed.get("nombres", [])
        if len(corregidos) == len(platos):
            _cache_normalizacion[cache_key] = corregidos
        else:
            return platos

    if len(corregidos) != len(platos):
        return platos

    fusionados: dict = {}
    for i, nombre_corr in enumerate(corregidos):
        nombre_corr = nombre_corr.lower().strip()
        fusionados[nombre_corr] = fusionados.get(nombre_corr, 0) + platos[i][1]
    return sorted(fusionados.items(), key=lambda x: -x[1])


def extraer_platos(serie_reviews, n: int = 5, nombre_restaurante: str = '') -> list:
    """
    Extrae nombres de platos de las reseñas usando tres estrategias:
      1. Whitelist directa (platos conocidos mencionados en ≥2 reseñas).
      2. Bigramas de sustantivos (ambas palabras fuera de NO_PLATOS).
      3. Trigramas con preposición central (ej: 'lomo de buey').
    Devuelve lista de (nombre, menciones) ordenada por frecuencia.
    """
    _NUNCA = NO_PLATOS | STOP_ES | set(ADJETIVOS_INICIO) | {
        'pedi','pedimos','probe','probamos','tome','tomamos','cenamos','comimos',
        'recomiendo','recomendamos','trajeron','pusieron','traen','ponen',
        'hacen','sirven','tienen','pedido','probado','tomado','cenado',
        'divino','divina','genial','increible','espectacular','agradable',
        'bonito','bonita','solo','sólo','verdad','gusta','encantan',
        'restaurante','local','sitio','barra','rueda','marca',
        'rico','rica','bueno','buena','malo','mala','mejor','peor',
    }

    freq_whitelist = Counter()
    freq_bigramas  = Counter()
    freq_res_wl    = Counter()
    freq_res_bg    = Counter()

    for resena in serie_reviews:
        texto    = limpiar(str(resena))
        palabras = re.findall(r'[a-záéíóúüñ]+', texto)
        vis_wl   = set()
        vis_bg   = set()

        for i, p in enumerate(palabras):
            # 1. Whitelist directa
            if p in PLATOS_WHITELIST:
                freq_whitelist[p] += 1
                if p not in vis_wl:
                    freq_res_wl[p] += 1
                    vis_wl.add(p)
            # 2. Bigramas
            if i < len(palabras) - 1:
                a, b = palabras[i], palabras[i + 1]
                if a not in _NUNCA and b not in _NUNCA and len(a) >= 3 and len(b) >= 3:
                    bg = f'{a} {b}'
                    freq_bigramas[bg] += 1
                    if bg not in vis_bg:
                        freq_res_bg[bg] += 1
                        vis_bg.add(bg)
            # 3. Trigramas con preposición
            if i < len(palabras) - 2:
                a, prep, c = palabras[i], palabras[i + 1], palabras[i + 2]
                if (prep in ('de', 'a', 'al', 'con', 'en', 'y')
                        and a not in _NUNCA and c not in _NUNCA
                        and len(a) >= 3 and len(c) >= 3):
                    tg = f'{a} {prep} {c}'
                    freq_bigramas[tg] += 1
                    if tg not in vis_bg:
                        freq_res_bg[tg] += 1
                        vis_bg.add(tg)

    # Combinar whitelist + bigramas, evitando solapamientos
    wl_cubiertas = {w for bg, _ in freq_bigramas.items() for w in bg.split()
                    if w in PLATOS_WHITELIST}
    candidatos = []
    for p, cnt in freq_res_wl.items():
        if cnt >= 2 or p in PLATOS_WHITELIST:
            mejor_bg = max(
                (freq_res_bg.get(bg, 0) for bg in freq_bigramas if p in bg.split()),
                default=0
            )
            if mejor_bg <= cnt:
                candidatos.append((p, cnt))
    for bg, cnt in freq_res_bg.items():
        if cnt >= 2:
            candidatos.append((bg, cnt))

    candidatos = [(t, c) for t, c in candidatos
                  if ' ' in t or t not in wl_cubiertas]
    candidatos.sort(key=lambda x: -x[1])

    # Filtrar blacklist y patrones inválidos antes de Gemini
    platos_sin_filtrar = [
        (t, c) for t, c in candidatos
        if t not in PLATOS_BLACKLIST
        and not any(p in _NUNCA for p in t.lower().split())
        and not PATRONES_NO_PLATO.search(t)
    ][:n * 3]

    platos_filtrados = filtrar_platos_con_gemini(platos_sin_filtrar, nombre_restaurante)
    platos_filtrados.sort(key=lambda x: -x[1])
    platos = platos_filtrados[:n]

    if MODO_ECONOMICO:
        return platos
    platos_norm = normalizar_platos(platos)
    platos_norm.sort(key=lambda x: -x[1])
    return platos_norm[:n]


def _extraer_freq_raw(serie_reviews) -> Counter:
    """
    Extrae frecuencias brutas de bigramas para completar platos faltantes
    sin reprocesar el modelo BERT (se usa en el modo de completado parcial).
    """
    freq_resenas = Counter()
    for r in serie_reviews:
        texto    = limpiar(str(r))
        palabras = re.findall(r"[a-záéíóúüñ]{3,}", texto)
        vistos   = set()
        for i in range(len(palabras) - 1):
            a, b = palabras[i], palabras[i + 1]
            if a not in NO_PLATOS and b not in NO_PLATOS:
                bg = f"{a} {b}"
                if bg not in vistos and not PATRONES_NO_PLATO.search(a) and not PATRONES_NO_PLATO.search(b):
                    vistos.add(bg)
        for p in palabras:
            if p in PLATOS_WHITELIST and p not in vistos:
                vistos.add(p)
        for t in vistos:
            freq_resenas[t] += 1
    return freq_resenas


# ═══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS DE SENTIMIENTO
# ═══════════════════════════════════════════════════════════════════════════════

def analizar_sentimiento_batch(textos: list, sentiment_pipeline) -> list:
    """
    Clasifica una lista de reseñas con el modelo nlptown.
    Devuelve lista de (estrellas, score, categoría) por reseña.
    """
    textos = [t if isinstance(t, str) and t.strip() else "sin texto" for t in textos]
    resultados = sentiment_pipeline(textos, truncation=True, max_length=512)
    out = []
    for r in resultados:
        e = int(r['label'].split()[0])
        out.append((e, round(r['score'], 3), estrellas_a_categoria(e)))
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# CRITERIOS CUALITATIVOS
# ═══════════════════════════════════════════════════════════════════════════════

def extraer_fragmentos(serie_reviews, keywords: list, ventana: int = 40) -> list:
    """
    Extrae fragmentos de contexto de las reseñas que contienen alguna keyword.
    Devuelve hasta 8 fragmentos únicos con `ventana` caracteres de contexto.
    """
    fragmentos = []
    vistos     = set()
    for resena in serie_reviews:
        texto       = str(resena)
        texto_lower = texto.lower()
        for kw in keywords:
            idx = texto_lower.find(kw)
            if idx == -1:
                continue
            inicio = max(0, idx - ventana)
            fin    = min(len(texto), idx + len(kw) + ventana)
            if inicio > 0:
                inicio = texto.rfind(' ', 0, inicio) + 1
            if fin < len(texto):
                fin = texto.find(' ', fin)
                if fin == -1:
                    fin = len(texto)
            frag = texto[inicio:fin].strip()
            if frag and frag not in vistos:
                vistos.add(frag)
                fragmentos.append(frag)
            if len(fragmentos) >= 8:
                return fragmentos
    return fragmentos


def clasificar_criterios_gemini(rid: int, nombre: str, serie_reviews: list) -> tuple:
    """
    Clasifica los criterios cualitativos usando Gemini sobre fragmentos relevantes.
    Estrategia de mínimo coste: una sola llamada con todos los criterios que tienen
    fragmentos, usando caché por id_restaurante para no repetir llamadas.
    Devuelve (dict de criterios True/False, dict de frases justificativas).
    """
    clave_cache = str(rid)
    if clave_cache in _cache_criterios:
        # En cache hit, recalcular frases sin coste adicional
        cached = _cache_criterios[clave_cache]
        frases = {}
        for criterio, keywords in CRITERIOS_SIGNAL.items():
            if cached.get(criterio):
                frags = extraer_fragmentos(serie_reviews, keywords)
                frags_ok = [f for f in frags if not tiene_negacion(f.lower(), keywords[0])]
                if frags_ok:
                    frases[criterio] = (parafrasear_frases(frags_ok[:2], CRITERIOS_DESC[criterio])
                                        if GEMINI_KEY else ' | '.join(frags_ok[:2]))
        return cached, frases

    resultado = {c: False for c in CRITERIOS_SIGNAL}

    # Paso 1: extraer fragmentos por criterio y filtrar negaciones obvias
    frags_por_criterio = {}
    for criterio, keywords in CRITERIOS_SIGNAL.items():
        frags = extraer_fragmentos(serie_reviews, keywords)
        frags_ok = [f for f in frags
                    if not any(tiene_negacion(f.lower(), kw) for kw in keywords)]
        if frags_ok:
            frags_por_criterio[criterio] = frags_ok

    if not frags_por_criterio:
        _cache_criterios[clave_cache] = resultado
        return resultado, {}

    # Paso 2: sin Gemini usar heurística de menciones
    if not GEMINI_KEY:
        for criterio in frags_por_criterio:
            resultado[criterio] = True
        frases = {c: ' | '.join(frags_por_criterio[c][:2]) for c in frags_por_criterio}
        _cache_criterios[clave_cache] = resultado
        return resultado, frases

    # Paso 3: una sola llamada a Gemini con todos los criterios
    secciones = []
    for criterio, frags in frags_por_criterio.items():
        desc       = CRITERIOS_DESC[criterio]
        frags_txt  = ' | '.join(f'"{f}"' for f in frags[:5])
        secciones.append(f'- {criterio} ({desc}):\n  {frags_txt}')

    criterios_lista = list(frags_por_criterio.keys())
    vals_default    = ", ".join(f'"{c}": false' for c in criterios_lista)
    prompt = (
        f'Rest: {nombre}\n'
        + '\n'.join(secciones)
        + '\ntrue=confirmado positivamente en los fragmentos. false=duda/negación.\n'
        f'JSON SOLO: {{{vals_default}}}'
    )

    parsed = gemini_json(prompt, max_tokens=100)
    for criterio in criterios_lista:
        val = parsed.get(criterio)
        if isinstance(val, bool):
            resultado[criterio] = val
        elif isinstance(val, str):
            resultado[criterio] = val.lower() == 'true'

    # Generar frases justificativas para los criterios activos
    frases = {}
    for criterio, frags in frags_por_criterio.items():
        if resultado.get(criterio):
            frases[criterio] = parafrasear_frases(frags[:2], CRITERIOS_DESC[criterio])

    _cache_criterios[clave_cache] = resultado
    return resultado, frases


# ═══════════════════════════════════════════════════════════════════════════════
# PERSONAL DESTACADO
# ═══════════════════════════════════════════════════════════════════════════════

def clasificar_nombres(candidatos: list) -> set:
    """
    Identifica cuáles de los candidatos son nombres de persona usando Gemini.
    Usa caché para no repetir clasificaciones ya conocidas.
    """
    por_consultar = [t for t in candidatos if t not in _cache_nombres]
    if por_consultar and GEMINI_KEY:
        prompt = (
            f"¿Cuáles de estas palabras son nombres propios de persona (en español)? {por_consultar}\n"
            'JSON SOLO: {"nombres": ["nombre1", ...]}'
        )
        parsed   = gemini_json(prompt, max_tokens=80)
        nombres  = set(parsed.get("nombres", []))
        for t in por_consultar:
            _cache_nombres[t] = t in nombres
    return {t for t in candidatos if _cache_nombres.get(t, False)}


def extraer_personal(serie_reviews, platos_set: set, n_resenas: int, n: int = 5) -> list:
    """
    Extrae nombres del personal mencionado positivamente en las reseñas.
    Filtra stopwords, nombres de platos y términos genéricos. Usa Gemini
    para confirmar que los candidatos son nombres propios de persona.
    """
    freq_total   = Counter()
    freq_resenas = Counter()
    for r in serie_reviews:
        texto    = limpiar(str(r))
        palabras = re.findall(r"[a-záéíóúüñ]{4,}", texto)
        tokens_set = set()
        for t in palabras:
            if t not in STOP_ES and t not in NO_PLATOS and t not in platos_set:
                freq_total[t] += 1
                tokens_set.add(t)
        for t in tokens_set:
            freq_resenas[t] += 1

    candidatos = [
        (t, freq_total[t]) for t in freq_total
        if freq_resenas.get(t, 0) >= 2
        and freq_resenas.get(t, 0) <= n_resenas * 0.40
    ]
    candidatos.sort(key=lambda x: -x[1])
    nombres   = clasificar_nombres([t for t, _ in candidatos[:30]])
    personal  = [(t, c) for t, c in candidatos if t in nombres]
    return personal[:n]


def extraer_personal_por_patrones(resenas: list, n: int = 3) -> list:
    """
    Extrae nombres de personal usando patrones de mención directa en contexto de servicio.
    Alternativa a extraer_personal cuando no se quiere usar el modelo BERT.
    Devuelve lista de strings con formato 'Nombre(menciones)'.
    """
    MIN_RESENAS = 2
    contador    = Counter()
    for resena in resenas:
        texto       = normalizar_texto(str(resena or ''))
        encontrados = set()
        for patron in PATRONES_PERSONAL:
            for match in re.finditer(patron, texto):
                for grupo in match.groups():
                    if grupo:
                        nombre = grupo.strip()
                        if (nombre not in STOP_PERSONAL
                                and len(nombre) >= 3
                                and len(nombre) <= 12
                                and nombre.isalpha()):
                            encontrados.add(nombre)
        for nombre in encontrados:
            contador[nombre] += 1

    return [f"{nombre.capitalize()}({count})"
            for nombre, count in contador.most_common(n * 2)
            if count >= MIN_RESENAS][:n]


# ═══════════════════════════════════════════════════════════════════════════════
# DETECCIÓN DE COCINA Y CATEGORÍA
# ═══════════════════════════════════════════════════════════════════════════════

def _parsear_platos_con_frecuencia(todos_platos: str) -> dict:
    """Convierte 'croquetas(34), pulpo(21)' en {'croquetas': 34, 'pulpo': 21}."""
    platos = {}
    for p in str(todos_platos).split(','):
        m = re.match(r'^(.+?)\((\d+)\)$', p.strip())
        if m:
            platos[normalizar_texto(m.group(1).strip())] = int(m.group(2))
    return platos


def detectar_cocina(nombre: str, todos_platos: str) -> str:
    """
    Detecta la cocina de un restaurante en dos capas:
      1. Por keywords en el nombre del restaurante.
      2. Por platos exclusivos de cada cocina con mínimo de menciones.
    Devuelve cadena vacía si no hay señal clara.
    """
    nombre_n = normalizar_texto(str(nombre))

    # Capa 1: nombre del restaurante
    for cocina, kws in NOMBRE_KEYWORDS_COCINA.items():
        if any(kw in nombre_n for kw in kws):
            return cocina

    # Capa 2: platos representativos
    platos = _parsear_platos_con_frecuencia(todos_platos)
    if not platos:
        return ''

    total       = sum(platos.values())
    mejor, mejor_score = '', 0.0
    for cocina, defs in PLATOS_POR_COCINA.items():
        matches, menciones = [], 0
        for d in defs:
            dn = normalizar_texto(d)
            for pr, mn in platos.items():
                if dn == pr or (len(dn) > 5 and dn in pr):
                    if mn >= 2:
                        matches.append(mn)
                        menciones += mn
                    break
        if len(matches) < 2:
            if cocina == 'asturiana' and any(m >= 5 for m in matches):
                pass
            else:
                continue
        if menciones / total < 0.25:
            continue
        score = sum(2 + math.log2(m) for m in matches)
        if score > mejor_score:
            mejor_score, mejor = score, cocina

    return mejor


def detectar_categoria(nombre: str, todos_platos: str, cocina_detectada: str) -> str:
    """
    Detecta la categoría de carta del restaurante (asador, marisquería, japonés…).
    Primero mira el nombre, luego los platos, y finalmente infiere desde la cocina.
    """
    nombre_n = normalizar_texto(str(nombre))

    # Mapa de cocina a categoría
    mapa_cocina = {
        'italiana': 'italiano', 'japonesa': 'japones', 'india': 'indio',
        'mexicana': 'mexicano', 'peruana': 'peruano', 'venezolana': 'venezolano',
        'argentina': 'argentino', 'tailandesa': 'tailandes', 'arabe': 'arabe',
        'vasca': 'taberna', 'madrileña': 'taberna', 'gallega': 'taberna',
        'asturiana': 'taberna', 'andaluza': 'taberna', 'fusion': 'fusion',
        'americana': 'hamburgueseria',
    }

    # Capa 1: nombre del restaurante
    for cocina, kws in NOMBRE_KEYWORDS_COCINA.items():
        if any(kw in nombre_n for kw in kws):
            return mapa_cocina.get(cocina, cocina)

    # Capa 2: platos
    platos = _parsear_platos_con_frecuencia(todos_platos)
    if platos:
        total = sum(platos.values())
        mejor, mejor_score = '', 0.0
        for categoria, defs in PLATOS_CATEGORIA.items():
            matches, menciones = [], 0
            min_p = 3 if categoria == 'marisqueria' else 2
            for d in defs:
                dn = normalizar_texto(d)
                for pr, mn in platos.items():
                    if dn == pr or (len(dn) > 5 and dn in pr):
                        if mn >= 3:
                            matches.append(mn)
                            menciones += mn
                        break
            if len(matches) < min_p or menciones / total < 0.20:
                continue
            score = sum(2 + math.log2(m) for m in matches)
            if score > mejor_score:
                mejor_score, mejor = score, categoria
        if mejor:
            return mejor

    # Capa 3: inferir desde cocina detectada
    return mapa_cocina.get(str(cocina_detectada), '')


# ═══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS COMPLETO POR RESTAURANTE
# ═══════════════════════════════════════════════════════════════════════════════

def analizar_restaurante(df_r: pd.DataFrame, sentiment_pipeline) -> tuple:
    """
    Realiza el análisis NLP completo de un restaurante:
      - Sentimiento por reseña (nlptown/bert)
      - Estadísticas por dimensión (servicio, comida, ambiente…)
      - Criterios cualitativos (Gemini)
      - Extracción de platos (whitelist + bigramas + Gemini)
      - Personal destacado
      - TF-IDF de términos representativos
    Devuelve (fila_resumen dict, df_resenas_con_sentimiento).
    """
    nombre    = df_r['Restaurante'].iloc[0]
    rid       = int(df_r['Id_Restaurante'].iloc[0])
    direccion = df_r['Direccion'].iloc[0] if 'Direccion' in df_r.columns else ''
    valoracion = df_r['Valoracion'].mean()
    n          = len(df_r)

    # ── Sentimiento ───────────────────────────────────────────────────────────
    textos    = df_r['Review'].astype(str).tolist()
    sent_res  = []
    for i in range(0, len(textos), BATCH_SIZE):
        sent_res += analizar_sentimiento_batch(textos[i:i + BATCH_SIZE], sentiment_pipeline)

    df_r = df_r.copy()
    df_r['estrellas']      = [x[0] for x in sent_res]
    df_r['score_modelo']   = [x[1] for x in sent_res]
    df_r['sentimiento']    = [x[2] for x in sent_res]
    df_r['baja_confianza'] = df_r['score_modelo'] < MIN_CONFIANZA

    sent_global    = Counter(df_r['sentimiento'])
    estrellas_dist = Counter(df_r['estrellas'])
    avg_stars      = round(df_r['estrellas'].mean(), 3)
    total_sent     = sum(sent_global.values())
    pct_pos = round(sent_global.get('positivo', 0) / total_sent * 100, 1)
    pct_neg = round(sent_global.get('negativo', 0) / total_sent * 100, 1)
    pct_neu = round(sent_global.get('neutro', 0) / total_sent * 100, 1)
    n_baja  = int(df_r['baja_confianza'].sum())

    # ── Dimensiones ───────────────────────────────────────────────────────────
    dim_data = {}
    for dim, kws in DIMENSIONES_KEYWORDS.items():
        menciones = sum(1 for r in df_r['Review'] if any(kw in limpiar(str(r)) for kw in kws))
        subset    = df_r[df_r['Review'].apply(lambda x: any(kw in limpiar(str(x)) for kw in kws))]
        sc        = Counter(subset['sentimiento'])
        avg_e     = round(subset['estrellas'].mean(), 2) if len(subset) else None
        dim_data[dim] = {
            'menciones': menciones,
            'pct':       round(menciones / n * 100, 1),
            'positivo':  sc.get('positivo', 0),
            'negativo':  sc.get('negativo', 0),
            'neutro':    sc.get('neutro', 0),
            'avg_stars': avg_e,
            'rep':       menciones >= MIN_MENCIONES,
        }

    # ── Criterios cualitativos ────────────────────────────────────────────────
    criterios, criterios_frases = clasificar_criterios_gemini(rid, nombre, df_r['Review'].tolist())
    criterios_log = ', '.join(f'{k}={"✓" if v else "✗"}' for k, v in criterios.items())
    print(f"    criterios: {criterios_log}")

    # ── Platos ────────────────────────────────────────────────────────────────
    platos_todos = extraer_platos(df_r['Review'], n=15, nombre_restaurante=nombre)
    platos_todos = _dedup_local(platos_todos)[:15]

    # Segundo barrido: recuperar platos de whitelist con ≥3 menciones no detectados
    platos_ya = {limpiar(p) for p, _ in platos_todos}
    for plato_wl in sorted(PLATOS_WHITELIST):
        plato_limpio = limpiar(plato_wl)
        if len(plato_limpio) < 4:
            continue
        if any(plato_limpio in det or det in plato_limpio for det in platos_ya):
            continue
        menciones = sum(1 for r in df_r['Review'].astype(str) if plato_limpio in limpiar(r))
        if menciones >= 3:
            platos_todos.append((plato_wl, menciones))
            platos_ya.add(plato_limpio)

    platos_todos.sort(key=lambda x: -x[1])
    platos_todos  = platos_todos[:15]
    platos_set    = {p for p, _ in platos_todos}
    platos_top    = platos_todos[:5]
    platos_str    = ', '.join([f"{p}({c})" for p, c in platos_top])
    todos_str     = ', '.join([f"{p}({c})" for p, c in platos_todos])

    # ── Personal destacado ────────────────────────────────────────────────────
    if not MODO_ECONOMICO:
        personal     = extraer_personal(df_r['Review'], platos_set, n)
        personal_str = ', '.join([f"{t.capitalize()}({c})" for t, c in personal])
    else:
        personal_str = ''

    # ── Frases de servicio ────────────────────────────────────────────────────
    kws_servicio = DIMENSIONES_KEYWORDS.get('servicio', [])
    frags_serv   = extraer_fragmentos(df_r['Review'].tolist(), kws_servicio, ventana=50)
    frags_serv_ok = [f for f in frags_serv if not tiene_negacion(f.lower(), 'servicio')]
    servicio_frases = (parafrasear_frases(frags_serv_ok[:3], f"el servicio de {nombre}")
                       if frags_serv_ok else '')

    # ── Reseñas destacadas ────────────────────────────────────────────────────
    resenas_destacadas = ''
    if GEMINI_KEY:
        df_pos = df_r[df_r['estrellas'] >= 4].copy()
        df_pos['_len'] = df_pos['Review'].astype(str).apply(len)
        df_pos = df_pos.sort_values('_len', ascending=False).head(5)
        if len(df_pos) > 0:
            frags = df_pos['Review'].astype(str).tolist()[:3]
            frags_txt = " | ".join(f[:150] for f in frags)
            prompt = (
                f"Resume en 3 frases cortas y naturales las mejores opiniones de clientes "
                f"sobre el restaurante {nombre}. Cada frase separada por ' | '. "
                f"Sin comillas, sin nombres propios, sin reproducir texto literal.\n"
                f"Opiniones: {frags_txt}\nResumen:"
            )
            resenas_destacadas = gemini_texto(prompt, max_tokens=120)

    # ── TF-IDF ────────────────────────────────────────────────────────────────
    textos_limpios = df_r['Review'].apply(limpiar).tolist()
    try:
        vec = TfidfVectorizer(stop_words=list(STOP_ES), min_df=2,
                              max_features=50, ngram_range=(1, 2))
        X   = vec.fit_transform(textos_limpios)
        mt  = np.asarray(X.mean(axis=0)).flatten()
        ti  = mt.argsort()[::-1][:5]
        tfidf_str = ', '.join(vec.get_feature_names_out()[ti])
    except Exception:
        tfidf_str = ''

    # ── Construir fila de resultado ───────────────────────────────────────────
    fila = {
        'id_restaurante':       rid,
        'nombre':               nombre,
        'direccion':            direccion,
        'n_resenas':            n,
        'valoracion_google':    round(valoracion, 2),
        'avg_estrellas_modelo': avg_stars,
        'pct_positivo':         pct_pos,
        'pct_neutro':           pct_neu,
        'pct_negativo':         pct_neg,
        'n_resenas_negativas':  sent_global.get('negativo', 0),
        'n_baja_confianza':     n_baja,
        'estrellas_5':          estrellas_dist.get(5, 0),
        'estrellas_4':          estrellas_dist.get(4, 0),
        'estrellas_3':          estrellas_dist.get(3, 0),
        'estrellas_2':          estrellas_dist.get(2, 0),
        'estrellas_1':          estrellas_dist.get(1, 0),
        **{f'{d}_menciones': dim_data[d]['menciones'] for d in DIMENSIONES_KEYWORDS},
        **{f'{d}_pct':        dim_data[d]['pct']       for d in DIMENSIONES_KEYWORDS},
        **{f'{d}_pos':        dim_data[d]['positivo']  for d in DIMENSIONES_KEYWORDS},
        **{f'{d}_neg':        dim_data[d]['negativo']  for d in DIMENSIONES_KEYWORDS},
        **{f'{d}_avg_stars':  dim_data[d]['avg_stars'] for d in DIMENSIONES_KEYWORDS},
        **{f'{d}_rep':        dim_data[d]['rep']       for d in DIMENSIONES_KEYWORDS},
        **{f'criterio_{c}': criterios[c] for c in CRITERIOS_SIGNAL},
        **{f'criterio_{c}_frases': criterios_frases.get(c, '') for c in CRITERIOS_SIGNAL},
        'servicio_frases':      servicio_frases,
        'resenas_destacadas':   resenas_destacadas,
        'top5_platos':          platos_str,
        'todos_platos':         todos_str,
        'personal_destacado':   personal_str,
        'terminos_tfidf':       tfidf_str,
        'cocina_detectada':     detectar_cocina(todos_str, nombre),
    }

    df_r_out = df_r[['Id_Restaurante', 'Restaurante', 'Id_review', 'Review',
                      'Valoracion', 'estrellas', 'score_modelo',
                      'sentimiento', 'baja_confianza']].copy()
    return fila, df_r_out


# ═══════════════════════════════════════════════════════════════════════════════
# GEOCODIFICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def geocodificar_restaurantes():
    """
    Lee ranking.csv, geocodifica las direcciones con Nominatim (OpenStreetMap, sin API key)
    y guarda restaurantes_geo.csv con columnas: Id_Restaurante, latitud, longitud.
    Es incremental: solo geocodifica los IDs que faltan si el archivo ya existe.
    """
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    except ImportError:
        print("ERROR: instala geopy con: pip install geopy")
        return

    PAUSA = 1.1
    geolocator = Nominatim(user_agent="RestaurantesMadridTFM/1.0")

    def _geocodificar_uno(direccion: str, nombre: str) -> tuple:
        """Intenta geocodificar una dirección con hasta 3 candidatos de consulta."""
        candidatos = [
            f"{direccion}, Madrid, España",
            f"{nombre}, Madrid, España",
            f"{direccion}, Madrid",
        ]
        for consulta in candidatos:
            for intento in range(3):
                try:
                    loc = geolocator.geocode(consulta, timeout=5)
                    if loc:
                        return round(loc.latitude, 7), round(loc.longitude, 7)
                    break
                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    print(f"    ⚠️  Intento {intento + 1}/3: {e}")
                    _time.sleep(2)
            _time.sleep(PAUSA)
        return None, None

    ranking = pd.read_csv(CSV_RANKING, sep=";", skiprows=1)
    ranking.columns = ranking.columns.str.strip()
    print(f"Restaurantes en ranking: {len(ranking)}")

    if os.path.exists(OUTPUT_GEO):
        geo_prev = pd.read_csv(OUTPUT_GEO)
        ids_ya   = set(geo_prev["Id_Restaurante"].tolist())
        filas    = geo_prev.to_dict("records")
        print(f"Ya geocodificados: {len(ids_ya)}")
    else:
        ids_ya = set()
        filas  = []

    pendientes = ranking[~ranking["Id_Restaurante"].isin(ids_ya)]
    print(f"Pendientes: {len(pendientes)}\n")

    for _, row in pendientes.iterrows():
        id_r      = int(row["Id_Restaurante"])
        nombre    = str(row.get("Restaurante", "") or "")
        direccion = str(row.get("Dirección", "") or "")

        if not direccion or direccion == "nan":
            print(f"  [{id_r}] {nombre} — sin dirección, saltando")
            filas.append({"Id_Restaurante": id_r, "latitud": None, "longitud": None})
            continue

        print(f"  [{id_r}] {nombre} ({direccion}) ... ", end="", flush=True)
        lat, lon = _geocodificar_uno(direccion, nombre)
        print(f"✓ {lat}, {lon}" if lat else "✗ no encontrado")

        filas.append({"Id_Restaurante": id_r, "latitud": lat, "longitud": lon})
        pd.DataFrame(filas).sort_values("Id_Restaurante").to_csv(OUTPUT_GEO, index=False)
        _time.sleep(PAUSA)

    resultado = pd.DataFrame(filas).sort_values("Id_Restaurante")
    resultado.to_csv(OUTPUT_GEO, index=False)
    con_coords = resultado["latitud"].notna().sum()
    print(f"\n✅ Completado: {con_coords}/{len(resultado)} restaurantes geocodificados")


# ═══════════════════════════════════════════════════════════════════════════════
# ETAPAS DEL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def etapa_analisis_nlp():
    """
    Etapa principal: carga las reseñas, ejecuta el análisis NLP completo para
    cada restaurante y guarda analisis_restaurantes.csv con checkpoint incremental.
    Usa el modelo nlptown/bert para sentimiento y Gemini para criterios y platos dudosos.
    """
    print("=" * 60)
    print("Cargando modelo nlptown...")
    sentiment_pipeline = hf_pipeline(
        "sentiment-analysis", model=MODELO_HF,
        truncation=True, max_length=512, batch_size=BATCH_SIZE,
    )
    print("Modelo listo.\n")

    if GEMINI_KEY:
        modo = "económico" if MODO_ECONOMICO else "completo"
        print(f"✔ Gemini configurado: {GEMINI_MODEL} (modo {modo})")
    else:
        print("⚠️  Sin GEMINI_API_KEY — modo heurístico")
    print()

    # Cargar reseñas
    df = pd.read_csv(CSV_RESENAS)
    n_antes = len(df)
    df['Review'] = df['Review'].astype(str).str.strip()
    df = df[df['Review'].str.lower() != 'nan']
    df = df[df['Review'] != '']
    print(f"Reseñas cargadas  : {n_antes}")
    print(f"Reseñas válidas   : {len(df)}\n")

    # Enriquecer con direcciones del ranking
    if os.path.exists(CSV_RANKING):
        df_ranking = pd.read_csv(CSV_RANKING, sep=';', skiprows=1)
        df_ranking = df_ranking[['Id_Restaurante', 'Dirección']].dropna(subset=['Dirección'])
        df_ranking = df_ranking.rename(columns={'Dirección': 'Direccion'})
        df = df.merge(df_ranking, on='Id_Restaurante', how='left')
        df['Direccion'] = df['Direccion'].fillna('')
        n_dir = (df.groupby('Id_Restaurante')['Direccion'].first() != '').sum()
        print(f"Direcciones cargadas: {n_dir} restaurantes\n")
    else:
        df['Direccion'] = ''
        print('⚠️  ranking.csv no encontrado — direcciones vacías\n')

    ids_todos = sorted(df['Id_Restaurante'].unique())

    # Checkpoint: determinar qué restaurantes ya están procesados
    ids_procesados = set()
    filas_resumen  = []
    filas_resenas  = []
    ids_completar  = set()

    if os.path.exists(OUTPUT_CSV):
        df_prev = pd.read_csv(OUTPUT_CSV)
        cols_esperadas = (
            [f'{d}_menciones' for d in DIMENSIONES_KEYWORDS] +
            [f'criterio_{c}' for c in CRITERIOS_SIGNAL]
        )
        cols_faltantes = [c for c in cols_esperadas if c not in df_prev.columns]

        if cols_faltantes:
            print(f"⚠️  Columnas nuevas detectadas — reprocesando todo.")
        else:
            def _contar_platos(val):
                return len(re.findall(r'\(\d+\)', str(val))) if not pd.isna(val) else 0

            df_prev['_n_platos'] = df_prev['top5_platos'].apply(_contar_platos)
            ids_completos  = set(df_prev[df_prev['_n_platos'] >= 5]['id_restaurante'].astype(int))
            ids_completar  = set(df_prev[
                (df_prev['_n_platos'] >= 1) & (df_prev['_n_platos'] < 5)
            ]['id_restaurante'].astype(int))
            ids_procesados = ids_completos
            filas_resumen  = df_prev[df_prev['id_restaurante'].astype(int).isin(ids_completos)] \
                                .drop(columns=['_n_platos'], errors='ignore').to_dict('records')
            print(f"CSV existente: {len(ids_completos)} completos · "
                  f"{len(ids_completar)} a completar · "
                  f"{len(ids_todos) - len(ids_completos) - len(ids_completar)} pendientes")

    if os.path.exists(OUTPUT_RESENAS) and ids_procesados:
        df_res_prev = pd.read_csv(OUTPUT_RESENAS)
        filas_resenas = [df_res_prev[df_res_prev['Id_Restaurante'].astype(int).isin(ids_procesados)]]

    # Completar restaurantes con 1-4 platos sin reprocesar BERT
    if ids_completar:
        print(f"\nCompletando {len(ids_completar)} restaurantes con platos incompletos...")
        df_completar = df_prev[df_prev['id_restaurante'].astype(int).isin(ids_completar)].copy()
        df_res_prev  = pd.read_csv(OUTPUT_RESENAS) if os.path.exists(OUTPUT_RESENAS) else None

        for _, row in df_completar.iterrows():
            rid         = int(row['id_restaurante'])
            nombre_r    = row['nombre']
            top5_actual = row['top5_platos'] if not pd.isna(row.get('top5_platos', '')) else ""
            resenas_r   = (df[df['Id_Restaurante'] == rid]['Review'].tolist() if df_res_prev is None
                           else df_res_prev[df_res_prev['Id_Restaurante'] == rid]['Review'].tolist())
            if not resenas_r:
                filas_resumen.append(row.drop(['_n_platos'], errors='ignore').to_dict())
                continue

            platos_actuales = [p.strip() for p in top5_actual.split(',')
                               if re.search(r'\(\d+\)', p.strip())]
            nombres_actuales = {re.sub(r'\(\d+\)$', '', p).strip().lower() for p in platos_actuales}
            faltan = 5 - len(platos_actuales)

            freq       = _extraer_freq_raw(resenas_r)
            candidatos = [(t, c) for t, c in freq.items() if c >= 2 and t not in nombres_actuales]
            candidatos.sort(key=lambda x: -x[1])
            nuevos     = filtrar_platos_con_gemini(candidatos[:faltan * 3], nombre_r)
            nuevos.sort(key=lambda x: -x[1])
            top5_nuevo = platos_actuales + [f"{p}({c})" for p, c in nuevos[:faltan]]

            if top5_nuevo and not MODO_ECONOMICO:
                parsed    = [(re.sub(r'\(\d+\)$', '', p).strip(),
                              int(re.search(r'\((\d+)\)$', p).group(1))) for p in top5_nuevo]
                top5_nuevo_norm = normalizar_platos(parsed)
                top5_nuevo_norm.sort(key=lambda x: -x[1])
                top5_str = ", ".join(f"{p}({c})" for p, c in top5_nuevo_norm[:5])
            else:
                top5_str = ", ".join(top5_nuevo[:5])

            fila_dict = row.drop(['_n_platos'], errors='ignore').to_dict()
            fila_dict['top5_platos'] = top5_str
            filas_resumen.append(fila_dict)
            print(f"  [{rid}] {nombre_r}: → {top5_str[:70]}")

        guardar_cache()

    # Procesar restaurantes pendientes con BERT
    ids_pendientes = [i for i in ids_todos
                      if int(i) not in ids_procesados and int(i) not in ids_completar]
    print(f"\nPendientes BERT: {len(ids_pendientes)}\n")
    cargar_cache()

    for i, rid in enumerate(ids_pendientes, 1):
        df_r     = df[df['Id_Restaurante'] == rid]
        nombre_r = df_r['Restaurante'].iloc[0]
        print(f"[{i}/{len(ids_pendientes)}] {rid}: {nombre_r} ({len(df_r)} reseñas)...")

        try:
            fila, df_res = analizar_restaurante(df_r, sentiment_pipeline)
            filas_resumen.append(fila)
            filas_resenas.append(df_res)

            pd.DataFrame(filas_resumen).sort_values('id_restaurante').to_csv(OUTPUT_CSV, index=False)
            pd.concat(filas_resenas).sort_values('Id_Restaurante').to_csv(OUTPUT_RESENAS, index=False)
            guardar_cache()

            print(f"    ✔ {fila['pct_positivo']}% pos | ★{fila['avg_estrellas_modelo']} | {fila['top5_platos'][:70]}")
            print(f"    💶 Coste estimado: €{coste_estimado():.4f}")
        except Exception as e:
            import traceback
            print(f"    ✗ Error: {e}")
            traceback.print_exc()

    # Post-procesado: segundo barrido de platos y cocina sobre el CSV final
    print("\nPost-procesando: recuperación de platos y cocina...")
    df_final = pd.read_csv(OUTPUT_CSV)
    df_res_final = pd.read_csv(OUTPUT_RESENAS) if os.path.exists(OUTPUT_RESENAS) else df

    actualizados_platos = 0
    actualizados_cocina = 0

    for idx, row in df_final.iterrows():
        rid      = int(row['id_restaurante'])
        nombre_r = str(row['nombre'])
        try:
            resenas_r = df_res_final[df_res_final['Id_Restaurante'] == rid]['Review'].astype(str).tolist()
        except Exception:
            resenas_r = df[df['Id_Restaurante'] == rid]['Review'].astype(str).tolist()
        if not resenas_r:
            continue

        todos_str = str(row.get('todos_platos', '') or '')
        platos_actuales = {}
        for parte in todos_str.split(','):
            m = re.match(r'^(.+?)\((\d+)\)$', parte.strip())
            if m:
                platos_actuales[limpiar(m.group(1).strip())] = int(m.group(2))

        # Segundo barrido whitelist
        nuevos = []
        for plato_wl in sorted(PLATOS_WHITELIST):
            plato_limpio = limpiar(plato_wl)
            if len(plato_limpio) < 4:
                continue
            if any(plato_limpio in det or det in plato_limpio for det in platos_actuales):
                continue
            menciones = sum(1 for r in resenas_r if plato_limpio in limpiar(str(r)))
            if menciones >= 3:
                nuevos.append((plato_wl, menciones))
                platos_actuales[plato_limpio] = menciones

        if nuevos:
            nuevos.sort(key=lambda x: -x[1])
            nuevos_str = ', '.join(f"{p}({c})" for p, c in nuevos)
            df_final.at[idx, 'todos_platos'] = (nuevos_str + ', ' + todos_str
                                                 if todos_str and todos_str != 'nan'
                                                 else nuevos_str)
            todos_str = df_final.at[idx, 'todos_platos']
            actualizados_platos += 1

        # Detectar cocina si no tiene
        cocina  = detectar_cocina(nombre_r, todos_str)
        current = str(row.get('cocina_detectada', '') or '')
        if cocina and current in ('', 'nan'):
            df_final.at[idx, 'cocina_detectada'] = cocina
            actualizados_cocina += 1
        elif not cocina and current in ('', 'nan'):
            df_final.at[idx, 'cocina_detectada'] = ''

        # Personal si está vacío
        personal_actual = str(row.get('personal_destacado', '') or '')
        if personal_actual in ('', 'nan'):
            personal = extraer_personal(resenas_r, set(platos_actuales.keys()), len(resenas_r), n=3)
            if personal:
                df_final.at[idx, 'personal_destacado'] = ', '.join(
                    f"{t.capitalize()}({c})" for t, c in personal
                )

    df_final.to_csv(OUTPUT_CSV, index=False)
    print(f"  Platos recuperados en {actualizados_platos} restaurantes")
    print(f"  Cocina detectada en {actualizados_cocina} restaurantes")
    print(f"\n{'=' * 60}\n¡Completado!\n  → {OUTPUT_CSV}\n  → {OUTPUT_RESENAS}")


def etapa_criterios():
    """
    Recalcula los criterios cualitativos (niños, terraza, romántico…)
    desde las reseñas sin usar Gemini ni reprocesar BERT.
    Actualiza directamente analisis_restaurantes.csv.
    """
    print("Recalculando criterios desde reseñas...")
    df      = pd.read_csv(OUTPUT_CSV)
    resenas = pd.read_csv(CSV_RESENAS)

    col_id  = next(c for c in resenas.columns if c.lower() == "id_restaurante")
    col_rev = next(c for c in resenas.columns if c.lower() in ("review", "texto", "resena"))
    resenas[col_id]      = resenas[col_id].astype(int).astype(str)
    df["id_restaurante"] = df["id_restaurante"].astype(int).astype(str)

    for criterio in CRITERIOS_SIGNAL:
        df[f"criterio_{criterio}"]        = False
        df[f"criterio_{criterio}_frases"] = ""

    def _limpiar_frase(texto: str) -> str:
        """Elimina conectores sueltos al inicio y asegura mayúscula y punto final."""
        texto = re.sub(r'^(y |e |pero |aunque |también |además )', '', texto.strip(), flags=re.IGNORECASE).strip()
        if not texto:
            return texto
        texto = texto[0].upper() + texto[1:]
        if texto[-1] not in ".!?":
            texto += "."
        return texto

    def _partir_segmentos(texto: str) -> list:
        """Divide el texto en segmentos por puntuación y conectores frecuentes."""
        patron = re.compile(
            r'[.!?\n]+'
            r'|,\s*(?=\w)'
            r'| y (?=(?:el |la |los |las |un |una |todo |muy |lo |también |además ))',
            re.IGNORECASE
        )
        cortes = [0]
        for m in patron.finditer(texto):
            cortes += [m.start(), m.end()]
        cortes.append(len(texto))
        cortes = sorted(set(cortes))
        return [(cortes[i], cortes[i + 1]) for i in range(len(cortes) - 1)
                if len(texto[cortes[i]:cortes[i + 1]].strip()) > 8]

    def _extraer_oracion(texto_orig: str, keyword_norm: str, max_chars: int = 120) -> str:
        """Extrae el segmento completo que contiene la keyword; descarta si no cabe."""
        texto_n = normalizar_texto(texto_orig)
        idx_n   = texto_n.find(keyword_norm)
        if idx_n == -1:
            return ""
        for ini, fin in _partir_segmentos(texto_orig):
            if ini <= idx_n < fin:
                fragmento = texto_orig[ini:fin].strip()
                if keyword_norm not in normalizar_texto(fragmento):
                    continue
                if len(fragmento) > max_chars:
                    return ""
                return _limpiar_frase(fragmento)
        return ""

    def _calcular_criterios(resenas_texto: list) -> tuple:
        """Calcula criterios booleanos y extrae frases justificativas."""
        resultado = {c: False for c in CRITERIOS_SIGNAL}
        frases    = {c: [] for c in CRITERIOS_SIGNAL}
        conteos   = defaultdict(int)

        for texto_orig in resenas_texto:
            texto_n = normalizar_texto(str(texto_orig))
            for criterio, keywords in CRITERIOS_SIGNAL.items():
                for kw in keywords:
                    kw_n = normalizar_texto(kw)
                    if kw_n in texto_n and not tiene_negacion(texto_n, kw_n):
                        conteos[criterio] += 1
                        if len(frases[criterio]) < 2:
                            oracion = _extraer_oracion(str(texto_orig), kw_n)
                            if oracion:
                                frases[criterio].append(oracion)
                        break

        for criterio in CRITERIOS_SIGNAL:
            if conteos[criterio] >= MIN_MENCIONES_CRITERIOS.get(criterio, 2):
                resultado[criterio] = True
        # Si True pero sin frases válidas, desactivar
        for criterio in CRITERIOS_SIGNAL:
            if resultado[criterio] and not frases[criterio]:
                resultado[criterio] = False

        return resultado, {c: " | ".join(v) for c, v in frases.items() if v and resultado[c]}

    print(f"  {len(df)} restaurantes | {len(resenas)} reseñas\n")
    for i, row in df.iterrows():
        rid    = str(row["id_restaurante"])
        nombre = str(row["nombre"])
        textos = resenas[resenas[col_id] == rid][col_rev].dropna().astype(str).tolist()

        resultado, frases = _calcular_criterios(textos)
        for criterio, valor in resultado.items():
            df.at[i, f"criterio_{criterio}"] = valor
        for criterio, frase in frases.items():
            df.at[i, f"criterio_{criterio}_frases"] = frase

        activos = [c for c, v in resultado.items() if v]
        print(f"[{i+1}/{len(df)}] {nombre[:40]:40} [{', '.join(activos) or 'ninguno'}]")

        if (i + 1) % 20 == 0:
            df.to_csv(OUTPUT_CSV, index=False)

    df.to_csv(OUTPUT_CSV, index=False)
    print("\n✔ Criterios actualizados.")


def etapa_personal():
    """
    Actualiza SOLO la columna personal_destacado en analisis_restaurantes.csv
    usando patrones de mención directa en las reseñas. Sin Gemini, sin BERT.
    """
    print("Actualizando personal destacado...")
    df_resenas  = pd.read_csv(CSV_RESENAS)
    df_analisis = pd.read_csv(OUTPUT_CSV)
    print(f"  {len(df_resenas)} reseñas · {len(df_analisis)} restaurantes\n")

    resultados = {}
    for rid in sorted(df_resenas['Id_Restaurante'].unique()):
        resenas = df_resenas[df_resenas['Id_Restaurante'] == rid]['Review'].tolist()
        nombres = extraer_personal_por_patrones(resenas)
        resultados[int(rid)] = ', '.join(nombres)
        if nombres:
            nombre_rest = df_resenas[df_resenas['Id_Restaurante'] == rid]['Restaurante'].iloc[0]
            print(f"  [{rid:>3}] {nombre_rest}: {', '.join(nombres)}")

    df_analisis['personal_destacado'] = df_analisis['id_restaurante'].apply(
        lambda x: resultados.get(int(x), '')
    )
    con_personal = (df_analisis['personal_destacado'] != '').sum()
    df_analisis.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✔ {con_personal}/{len(df_analisis)} restaurantes con personal identificado")


def etapa_frases():
    """
    Regenera SOLO las columnas servicio_frases y resenas_destacadas
    usando Gemini para obtener frases naturales sin texto literal.
    Requiere GEMINI_API_KEY configurada.
    """
    if not GEMINI_KEY:
        print("ERROR: GEMINI_API_KEY no configurada. Añádela al .env")
        return

    print("Regenerando frases con Gemini...")
    df      = pd.read_csv(OUTPUT_CSV)
    resenas = pd.read_csv(CSV_RESENAS)

    col_id  = next(c for c in resenas.columns if "id_restaurante" in c.lower())
    col_rev = next(c for c in resenas.columns if c.lower() in ("review", "texto", "resena"))
    col_val = next((c for c in resenas.columns if c.lower() in ("estrellas", "valoracion")), None)

    resenas[col_id]      = resenas[col_id].astype(str)
    df["id_restaurante"] = df["id_restaurante"].astype(str)

    def _es_cortada(texto: str) -> bool:
        t = str(texto).strip()
        return not t or t.lower() in ("nan", "none", "") or len(t) < 25

    nuevas_servicio   = []
    nuevas_destacadas = []

    for i, row in df.iterrows():
        rid    = str(row["id_restaurante"])
        nombre = str(row["nombre"])
        print(f"[{i+1}/{len(df)}] {nombre[:40]}...", end=" ", flush=True)
        df_r = resenas[resenas[col_id] == rid]

        # servicio_frases
        serv_actual = str(row.get("servicio_frases", "") or "")
        if _es_cortada(serv_actual):
            kws   = ["atención", "servicio", "amable", "trato", "camarero", "camarera", "personal"]
            frags = [str(rv[col_rev])[:180]
                     for _, rv in df_r.iterrows()
                     if any(k in str(rv[col_rev]).lower() for k in kws)][:3]
            if frags:
                frags_txt = " | ".join(frags)
                prompt = (
                    f"Reescribe en 2 frases naturales y completas lo que expresan estas opiniones "
                    f"sobre el servicio de {nombre}. Sin comillas, sin nombres propios, "
                    f"sin reproducir texto literal. Separa con ' | '.\n"
                    f"Opiniones: {frags_txt}\nFrases:"
                )
                serv_nuevo = gemini_texto(prompt, max_tokens=250)
                nuevas_servicio.append(serv_nuevo if not _es_cortada(serv_nuevo) else serv_actual)
            else:
                nuevas_servicio.append(serv_actual)
        else:
            nuevas_servicio.append(serv_actual)

        # resenas_destacadas
        dest_actual = str(row.get("resenas_destacadas", "") or "")
        if _es_cortada(dest_actual):
            df_pos = (df_r[pd.to_numeric(df_r[col_val], errors="coerce") >= 4].copy()
                      if col_val else df_r.copy())
            df_pos["_len"] = df_pos[col_rev].fillna("").astype(str).apply(len)
            df_pos = df_pos.sort_values("_len", ascending=False).head(4)
            if len(df_pos) > 0:
                frags     = df_pos[col_rev].astype(str).tolist()[:3]
                frags_txt = " | ".join(f[:200] for f in frags)
                prompt = (
                    f"Resume en 3 frases cortas y naturales las mejores opiniones de clientes "
                    f"sobre {nombre}. Cada frase separada por ' | '. "
                    f"Sin comillas, sin nombres propios, sin texto literal.\n"
                    f"Opiniones: {frags_txt}\nResumen:"
                )
                dest_nuevo = gemini_texto(prompt, max_tokens=350)
                nuevas_destacadas.append(dest_nuevo if not _es_cortada(dest_nuevo) else "")
            else:
                nuevas_destacadas.append("")
        else:
            nuevas_destacadas.append(dest_actual)

        print("✔")

    df["servicio_frases"]    = nuevas_servicio
    df["resenas_destacadas"] = nuevas_destacadas
    df.to_csv(OUTPUT_CSV, index=False)

    c_serv = sum(1 for v in nuevas_servicio  if _es_cortada(v))
    c_dest = sum(1 for v in nuevas_destacadas if _es_cortada(v))
    print(f"\n✔ servicio_frases:   {len(df)-c_serv}/{len(df)} correctas")
    print(f"✔ resenas_destacadas: {len(df)-c_dest}/{len(df)} correctas")


def etapa_cocina():
    """
    Recalcula cocina_detectada y categoria_carta para todos los restaurantes
    usando las listas de platos representativos y keywords de nombre.
    Sin Gemini, sin BERT. Actualiza analisis_restaurantes.csv.
    """
    print("Detectando cocina y categoría de carta...")
    df = pd.read_csv(OUTPUT_CSV)

    df['cocina_detectada'] = df.apply(
        lambda r: detectar_cocina(str(r['nombre']), str(r['todos_platos'])), axis=1
    )
    df['categoria_carta'] = df.apply(
        lambda r: detectar_categoria(r['nombre'], r['todos_platos'], r['cocina_detectada']), axis=1
    )

    print("DISTRIBUCIÓN cocina_detectada:")
    print(df['cocina_detectada'].replace('', '(sin categoría)').value_counts().to_string())
    print("\nDISTRIBUCIÓN categoria_carta:")
    print(df['categoria_carta'].replace('', '(sin categoría)').value_counts().to_string())

    df.to_csv(OUTPUT_CSV, index=False)
    print("\n✔ Guardado.")


# ═══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--solo-criterios" in args:
        etapa_criterios()
    elif "--solo-personal" in args:
        etapa_personal()
    elif "--solo-frases" in args:
        etapa_frases()
    elif "--solo-cocina" in args:
        etapa_cocina()
    elif "--solo-geo" in args:
        geocodificar_restaurantes()
    else:
        # Pipeline completo
        etapa_analisis_nlp()
        etapa_cocina()
        etapa_criterios()
        etapa_personal()
        print("\n🏁 Pipeline completo finalizado.")
