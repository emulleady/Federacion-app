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
    path("torneos/mis-inscripciones/", views.mis_inscripciones_torneo, name="mis_inscripciones_torneo"),
    path("torneos/formulario-12/", views.formulario_12, name="formulario_12"),
    path("formulario-07/", views.formulario_07, name="formulario_07"),
    path("torneos/mis-presentaciones/", views.mis_presentaciones_formulario12, name="mis_presentaciones_formulario12"),
    path("torneos/presentaciones/<int:presentacion_id>/subir/", views.subir_formulario12_firmado, name="subir_formulario12_firmado"),
    path("planilla/", views.planilla_partido, name="planilla_partido"),

    # Federación
    path("panel/", views.panel_solicitudes, name="panel_solicitudes"),
    path("panel/historial/", views.historial_solicitudes, name="historial_solicitudes"),
    path("panel/solicitud/<int:solicitud_id>/", views.revisar_solicitud, name="revisar_solicitud"),
    path("panel/solicitud/<int:solicitud_id>/formulario-09/", views.formulario_09, name="formulario_09"),
    path("panel/solicitud/<int:solicitud_id>/formulario-10/", views.formulario_10, name="formulario_10"),
    path("torneos/cobro-masivo/", views.cobro_masivo, name="cobro_masivo"),
    path("torneos/presentaciones/", views.presentaciones_formulario12, name="presentaciones_formulario12"),
    path("torneos/presentaciones/historial/", views.historial_presentaciones_formulario12, name="historial_presentaciones_formulario12"),
    path("torneos/presentaciones/<int:presentacion_id>/resolver/", views.resolver_presentacion_formulario12, name="resolver_presentacion_formulario12"),
    path("torneos/inscripciones/historial/", views.historial_inscripciones, name="historial_inscripciones"),
    path("torneos/cobrar/<int:inscripcion_id>/", views.cobrar_inscripcion, name="cobrar_inscripcion"),
    path("torneos/pagado/<int:inscripcion_id>/", views.marcar_pagado, name="marcar_pagado"),
    path("padron/", views.padron_club, name="padron_club"),
    path("padron/excel/", views.padron_excel, name="padron_excel"),
    path("padron/pdf/", views.padron_pdf, name="padron_pdf"),
    path("importar/", views.importar_excel, name="importar_excel"),

    # Ficha de jugador
    path("persona/<int:persona_id>/", views.ficha_persona, name="ficha_persona"),
    path("persona/<int:persona_id>/formulario-08/", views.formulario_08, name="formulario_08"),
    path("persona/<int:persona_id>/subir-autorizacion/", views.subir_autorizacion, name="subir_autorizacion"),
    path("buscar/", views.buscar_persona, name="buscar_persona"),

    # Tarjetas y sanciones
    path("tarjetas/cargar/", views.cargar_tarjeta, name="cargar_tarjeta"),
    path("tarjetas/sanciones/", views.sanciones_pendientes, name="sanciones_pendientes"),
    path("tarjetas/sanciones/<int:sancion_id>/resolver/", views.resolver_sancion, name="resolver_sancion"),
    path("tarjetas/mis-sanciones/", views.mis_sanciones, name="mis_sanciones"),
    path("tarjetas/mias/", views.mis_tarjetas, name="mis_tarjetas"),
    path("tarjetas/mis-sanciones/<int:sancion_id>/subir/", views.subir_comprobante_sancion, name="subir_comprobante_sancion"),

    # Consejo de disciplina
    path("disciplina/", views.panel_disciplina, name="panel_disciplina"),
    path("disciplina/<int:sancion_id>/resolver/", views.resolver_sancion_disciplinaria, name="resolver_sancion_disciplinaria"),
]
