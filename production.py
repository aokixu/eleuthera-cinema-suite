import re


CATEGORY_RULES = {
    'Vehiculo': ('auto', 'automovil', 'coche', 'camion', 'camioneta', 'bus', 'autobus', 'ambulancia', 'motocicleta', 'moto', 'bicicleta', 'taxi', 'tren', 'avion', 'barco'),
    'Utileria': ('arma', 'revolver', 'pistola', 'rifle', 'escopeta', 'cuchillo', 'espada', 'telefono', 'celular', 'carta', 'maleta', 'botella', 'vaso', 'taza', 'libro', 'llave', 'linterna', 'fotografia', 'computadora', 'radio', 'dinero', 'mochila'),
    'Vestuario': ('vestido', 'traje', 'uniforme', 'camisa', 'camiseta', 'pantalon', 'falda', 'abrigo', 'chaqueta', 'sombrero', 'gorra', 'zapato', 'bota', 'guante', 'mascara', 'lentes'),
    'Maquillaje y peluqueria': ('sangre', 'herida', 'cicatriz', 'moreton', 'tatuaje', 'maquillaje', 'barba', 'bigote', 'peluca', 'canas'),
    'Efecto especial': ('lluvia', 'nieve', 'niebla', 'humo', 'fuego', 'incendio', 'explosion', 'chispa', 'viento', 'destrozado', 'roto', 'disparo', 'choque'),
    'Animal': ('perro', 'gato', 'caballo', 'ave', 'pajaro', 'gallina', 'vaca', 'toro', 'oveja', 'serpiente', 'pez'),
    'Ambientacion': ('mesa', 'silla', 'sofa', 'cama', 'lampara', 'espejo', 'cuadro', 'reloj', 'alfombra', 'cortina', 'vela'),
    'Sonido y musica': ('musica', 'cancion', 'sirena', 'alarma', 'timbre', 'grito', 'trueno'),
    'Extra': ('multitud', 'gente', 'clientes', 'pasajeros', 'policias', 'soldados', 'periodistas', 'invitados', 'peatones', 'ninos'),
}

def normalize(value):
    import unicodedata
    return ''.join(char for char in unicodedata.normalize('NFD', value.lower())
                   if unicodedata.category(char) != 'Mn')


def analyze_blocks(blocks):
    suggestions = []
    seen = set()
    scene = 'Sin escena'
    for block in blocks:
        value = block.get('text', '').strip()
        if not value:
            continue
        block_type = block.get('type', 'action')
        if block_type == 'scene':
            scene = value
            from project_store import scene_fields
            _, _, location = scene_fields(value)
            add_suggestion(suggestions, seen, scene, 'Localizacion', location.title(), value)
            moment = next((word for word in ('DIA', 'NOCHE', 'AMANECER', 'ATARDECER') if word in normalize(value).upper()), '')
            if moment:
                add_suggestion(suggestions, seen, scene, 'Condicion de rodaje', moment.title(), value)
        elif block_type == 'character':
            add_suggestion(suggestions, seen, scene, 'Reparto', value.title(), value)
        elif block_type in ('action', 'dialogue', 'parenthetical'):
            normalized = normalize(value)
            for category, words in CATEGORY_RULES.items():
                for word in words:
                    if re.search(r'\b{}s?\b'.format(re.escape(word)), normalized):
                        add_suggestion(suggestions, seen, scene, category, word.title(), value)
    return suggestions


def add_suggestion(rows, seen, scene, category, element, source):
    if not element:
        return
    key = (scene, category, normalize(element))
    if key in seen:
        return
    seen.add(key)
    rows.append({'approved': False, 'scene': scene, 'category': category,
                 'element': element, 'source': source})



