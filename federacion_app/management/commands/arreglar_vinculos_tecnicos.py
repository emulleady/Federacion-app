from django.core.management.base import BaseCommand
from federacion_app.models import Vinculo


class Command(BaseCommand):
    help = (
        "Corrige, por única vez, el 'tipo' y 'rol_tecnico' de los vínculos que ya "
        "existían antes de que el rol pasara a vivir en el Vínculo en vez de en la "
        "Persona. Es seguro correrlo más de una vez (no rompe nada si ya está corregido)."
    )

    def handle(self, *args, **options):
        corregidos = 0
        for v in Vinculo.objects.select_related("persona").all():
            if v.persona.tipo == "tecnico" and v.tipo != "tecnico":
                v.tipo = "tecnico"
                v.rol_tecnico = v.persona.rol_tecnico
                v.save(update_fields=["tipo", "rol_tecnico"])
                corregidos += 1
        self.stdout.write(self.style.SUCCESS(f"Vínculos de técnicos corregidos: {corregidos}"))
