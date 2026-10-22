import { useFeatures } from '../../hooks/features'
import { t, useT } from '../../i18n'
import { ModelsPanel } from '../models/ModelsDialog'
import { WorkstationPanel } from '../workstation/WorkstationDialog'
import { Button } from '../ui/button'
import { Dialog, DialogPanel, DialogTrigger } from '../ui/dialog'

/** Explicit navigation only: opening this dialog never installs or starts anything. */
export function OmniSetup() {
  useT()
  const features = useFeatures()
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">{t('Instalar o configurar Omni')}</Button>
      </DialogTrigger>
      <DialogPanel title={t('Preparar FastH3 Omni')} description={t('Motor, perfil y modelo opcionales. Nada se descarga ni arranca automáticamente.')} className="w-[min(46rem,calc(100vw-1.5rem))]">
        <div className="space-y-4 text-xs leading-relaxed text-muted">
          <p>{t('Instala el perfil opcional')} <code>fasth3-omni</code> {t('con el instalador local. Después busca y elige esa instalación en el panel de abajo e inicia su motor. Omni usa su propio carril loopback 8237; no es FastH3 V2 ni cambia la receta Character Swap.')}</p>
          <p>{t('El modelo Omni es una descarga opcional fijada de aproximadamente 22,2 GB. En Modelos, revisa origen, revisión y SHA256 y confirma la licencia antes de descargar. También puedes verificar y reutilizar pesos existentes desde una carpeta autorizada, sin copiarlos. La instalación por defecto no descarga Omni.')}</p>
          {features.workstation ? <WorkstationPanel /> : <p role="note">{t('Este backend no ofrece controles de instalación. Ejecuta el instalador local con el perfil fasth3-omni y pide al administrador que configure el motor Omni en 127.0.0.1:8237.')}</p>}
          {features.models ? <ModelsPanel /> : <p role="note">{t('El gestor de modelos no está disponible en este backend. Abre Studio con el backend del paquete que ofrece Modelos; no se ha iniciado ninguna descarga.')}</p>}
        </div>
      </DialogPanel>
    </Dialog>
  )
}

export function OmniNotes() {
  useT()
  return (
    <div className="space-y-1 text-[11px] leading-snug text-faint">
      <p>{t('Escenas desde referencias de imagen: conserva su proporción. No necesita vídeo guía ni body_swap; no es la receta Character Swap.')}</p>
      <p>{t('Ejemplos de una imagen y 5,17 s: 86–123 s con motor caliente en RTX 4090. Arranque en frío y otras escenas pueden tardar más; no es un SLA ni garantía de HD.')}</p>
      <p>{t('El audio se genera con la escena: no es voz clonada ni garantiza conservar la identidad vocal.')}</p>
    </div>
  )
}
