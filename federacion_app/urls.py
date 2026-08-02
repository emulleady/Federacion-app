from django.urls import path
from . import views

urlpatterns = [
    path("", views.bienvenida, name="bienvenida"),
    path("inicio/", views.home, name="home"),

    # Delegado
    path("solicitudes/nueva/", views.nueva_solicitud, name="nueva_solicitud"),
    path("solicitudes/mias/", views.mis_solicitudes, name="mis_solicitudes"),
    path("solicitudes/mias/historial/", views.historial_mis_solicitudes, name="historial_mis_solicitudes"),
    path("solicitudes/liberar/", views.solicitudes_a_liberar, name="solicitudes_a_liberar"),
    path("solicitudes/liberar/<int:solicitud_id>/", views.liberar_solicitud, name="liberar_solicitud"),
    path("torneos/inscribir/", views.inscribir_torneo, name="inscribir_torneo"),
    path("torneos/formulario-12/", views.formulario_12, name="formulario_12"),
    path("planilla/", views.planilla_partido, name="planilla_partido"),

    # Federación
    path("panel/", views.panel_solicitudes, name="panel_solicitudes"),
    path("panel/historial/", views.historial_solicitudes, name="historial_solicitudes"),
    path("panel/solicitud/<int:solicitud_id>/", views.revisar_solicitud, name="revisar_solicitud"),
    path("torneos/cobro-masivo/", views.cobro_masivo, name="cobro_masivo"),
    path("torneos/inscripciones/historial/", views.historial_inscripciones, name="historial_inscripciones"),
    path("torneos/cobrar/<int:inscripcion_id>/", views.cobrar_inscripcion, name="cobrar_inscripcion"),
    path("torneos/pagado/<int:inscripcion_id>/", views.marcar_pagado, name="marcar_pagado"),
    path("padron/", views.padron_club, name="padron_club"),
    path("padron/excel/", views.padron_excel, name="padron_excel"),
    path("padron/pdf/", views.padron_pdf, name="padron_pdf"),
    path("importar/", views.importar_excel, name="importar_excel"),

    # Ficha de jugador
    path("persona/<int:persona_id>/", views.ficha_persona, name="ficha_persona"),
    path("buscar/", views.buscar_persona, name="buscar_persona"),
]
