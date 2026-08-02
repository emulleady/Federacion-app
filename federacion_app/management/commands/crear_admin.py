"""
Crea el primer usuario administrador (rol federación) usando variables
de entorno, para no depender de la Shell de Render (que es de pago).

Es seguro correrlo en cada deploy: si el usuario ya existe, no hace
nada (no lo duplica, no pisa la contraseña).

Variables de entorno que usa:
    ADMIN_USERNAME
    ADMIN_PASSWORD
Si no están seteadas, el comando no hace nada (no rompe el deploy).
"""

import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea el superusuario inicial de federación a partir de variables de entorno"

    def handle(self, *args, **options):
        from federacion_app.models import Usuario

        username = os.environ.get("ADMIN_USERNAME")
        password = os.environ.get("ADMIN_PASSWORD")

        if not username or not password:
            self.stdout.write("ADMIN_USERNAME / ADMIN_PASSWORD no están seteadas, se omite.")
            return

        if Usuario.objects.filter(username=username).exists():
            self.stdout.write(f"El usuario '{username}' ya existe, no se toca.")
            return

        Usuario.objects.create_superuser(
            username=username,
            password=password,
            rol="federacion",
        )
        self.stdout.write(self.style.SUCCESS(f"Usuario admin '{username}' creado correctamente."))
