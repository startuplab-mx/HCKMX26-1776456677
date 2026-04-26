import type { DemoStep } from '../hooks/useDemoMode'
import { GROOMING_STEPS, RECRUITMENT_STEPS } from '../hooks/useDemoMode'
type TimelineScenario = 'grooming' | 'recruitment'

const GROOMING_PHASES = [
  { label: 'Contacto', color: 'bg-green-500', steps: [0, 1] },
  { label: 'Sondeo', color: 'bg-yellow-500', steps: [2, 3] },
  { label: 'Manipulación', color: 'bg-orange-500', steps: [4, 5] },
  { label: 'Aislamiento', color: 'bg-red-500', steps: [6, 7] },
  { label: 'Solicitud', color: 'bg-red-700', steps: [8] },
]

const RECRUITMENT_PHASES = [
  { label: 'Acercamiento', color: 'bg-green-500', steps: [0, 1] },
  { label: 'Oferta', color: 'bg-yellow-500', steps: [2, 3] },
  { label: 'Negociación', color: 'bg-orange-500', steps: [4, 5] },
  { label: 'Reclutamiento', color: 'bg-red-700', steps: [6] },
]

interface Props {
  scenario: TimelineScenario
  currentStep: number
}

export function PatternTimeline({ scenario, currentStep }: Props) {
  const steps: DemoStep[] = scenario === 'grooming' ? GROOMING_STEPS : RECRUITMENT_STEPS

  const phases = scenario === 'grooming' ? GROOMING_PHASES : RECRUITMENT_PHASES
  const title = scenario === 'grooming' ? 'Patrón de Grooming' : 'Patrón de Reclutamiento'

  return (
    <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wide">{title}</span>
        <span className="text-[10px] text-gray-500 font-mono">{currentStep}/{steps.length} pasos</span>
      </div>

      {/* Phase indicators */}
      <div className="flex gap-1 mb-3">
        {phases.map((phase, pi) => {
          const done = phase.steps.every(s => s < currentStep)
          const active = phase.steps.some(s => s < currentStep) && !done
            || phase.steps.includes(currentStep - 1)
          return (
            <div key={pi} className="flex-1 text-center">
              <div className={`h-1.5 rounded-full mb-1 transition-all duration-500 ${done || active ? phase.color : 'bg-gray-700'}`} />
              <span className={`text-[9px] font-mono ${done || active ? 'text-gray-300' : 'text-gray-600'}`}>
                {phase.label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Step list */}
      <div className="space-y-1">
        {steps.map((step, idx) => {
          const done = idx < currentStep
          const active = idx === currentStep - 1
          return (
            <div
              key={idx}
              className={`flex items-start gap-2 px-2 py-1 rounded text-[10px] transition-all duration-300 ${
                active ? 'bg-yellow-500/15 border border-yellow-500/40' :
                done ? 'opacity-60' : 'opacity-30'
              }`}
            >
              <span className={`shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold mt-0.5 ${
                active ? 'bg-yellow-500 text-black' :
                done ? 'bg-green-700 text-white' : 'bg-gray-700 text-gray-500'
              }`}>
                {done && !active ? '✓' : idx + 1}
              </span>
              <div className="min-w-0">
                <span className={`font-semibold ${active ? 'text-yellow-300' : done ? 'text-gray-400' : 'text-gray-600'}`}>
                  {step.label}
                </span>
                {(done || active) && (
                  <p className={`truncate mt-0.5 ${active ? 'text-gray-200' : 'text-gray-500'}`}>
                    <span className="font-mono text-[9px] text-gray-500">{step.player}: </span>
                    {step.text}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
