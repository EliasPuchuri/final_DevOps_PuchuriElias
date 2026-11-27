# Distritos y sectores del formulario

Los sectores del catálogo usan la sectorización real de Miraflores. Los códigos `M01`–`M03` y la condición «habilitado» siguen siendo supuestos académicos del enunciado.

## Qué es real y qué es simulado

| Elemento | Origen |
|---|---|
| Tres sectores urbanos A, B y C de Miraflores y sus límites | **Real.** Plan de Desarrollo Local Concertado de la Municipalidad de Miraflores |
| Códigos `M01`, `M02`, `M03` | Simulado: los fija el enunciado (los casos P01–P11 los usan) |
| Qué sector está habilitado (`M03` = No) | Simulado: es un supuesto académico y **no refleja el servicio real** |
| Asignar cada código a un sector | Decisión de este proyecto (ver tabla) |

## Catálogo

| Código | Sector real | Límites según el Plan | Habilitado |
|---|---|---|---|
| `M01` | Sector B | Norte: San Isidro (Av. Santa Cruz y Av. Andrés Aramburú). Sur: Malecón 28 de Julio, Malecón de la Reserva y Malecón de Armendáriz. Este: Av. Paseo de la República (Vía Expresa) | Sí |
| `M02` | Sector C | Norte: San Isidro (Av. Angamos). Sur: Malecón La Marina y subsector B4. Corresponde a la urbanización Chacarilla Santa Cruz (Santa Isabel) | Sí |
| `M03` | Sector A | Norte y este: Surquillo (Av. Tomás Marzano). Sur: Santiago de Surco. Oeste: Av. Paseo de la República. Incluye las urbanizaciones San Antonio y Aurora | No (supuesto) |

## Distritos del formulario

Los valores `MIRAFLORES`, `SURQUILLO` y `OTRO` los fija el enunciado. Surquillo, San Isidro, Barranco y Santiago de Surco son los distritos con los que limita Miraflores según el Plan; el formulario agrupa los tres últimos bajo «Otro». Para Surquillo y «Otro» no se pide sector.

## Fuente y límites de esta información

- **Fuente:** Municipalidad Distrital de Miraflores, *Plan de Desarrollo Local Concertado*, sección «Sectorización del Distrito» (PDF publicado en miraflores.gob.pe; los metadatos del archivo indican 2016).
- **Alcance:** esos sectores se definieron para aplicar el índice de usos del suelo, **no** son la división operativa de la limpieza pública. No se encontró una división oficial de limpieza; la de Serenazgo (14 sectores) es de seguridad y sus cifras difieren entre documentos.
- **Antigüedad:** el documento es de 2016 y puede haber cambiado. Antes de presentar esto como dato vigente, confirmar con la municipalidad.
- **No usado:** el Plan menciona también una sectorización vecinal en un plano; no se pudo extraer su contenido.
- El Plan describe a Santa Cruz con un juicio de valor que no se reproduce aquí.
- No se verificó (la fuente no lo dice) en qué sector exacto quedan lugares como Parque Kennedy o Larcomar.

## Cómo aplicar el cambio de nombres en una base existente

```sh
psql -v ON_ERROR_STOP=1 -d miraflores -f db/updates/001_nombres_sectores.sql
```

Solo cambia el nombre; los códigos y la condición de habilitado no se modifican.
