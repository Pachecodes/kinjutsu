import { create } from 'zustand'

import { PREF_SHOW_EXPERIMENTAL, PREF_TOUR_DONE, readPref, writePref } from '../lib/prefs'

export type InspectorTab = 'references' | 'settings' | 'activity'
export type MobileView = 'compose' | 'stage' | 'refs' | 'gallery'

interface UiState {
  /** The take shown on the stage. Follows the newest render unless pinned. */
  selectedJobId: string | null
  /** The take this session submitted and is watching. */
  activeJobId: string | null
  inspectorTab: InspectorTab
  mobileView: MobileView
  showHidden: boolean
  /** Experimental and legacy recipes are opt-in and stay out of the front page. */
  showExperimental: boolean
  /** Guided tour: index of the open step, or null when closed. */
  tourStep: number | null
  /** The creator finished or dismissed the tour once; it never auto-offers again. */
  tourDone: boolean
  selectJob: (jobId: string | null) => void
  setActiveJob: (jobId: string | null) => void
  setInspectorTab: (tab: InspectorTab) => void
  setMobileView: (view: MobileView) => void
  setShowHidden: (show: boolean) => void
  setShowExperimental: (show: boolean) => void
  openTour: (step?: number) => void
  setTourStep: (step: number) => void
  closeTour: () => void
}

export const useUi = create<UiState>((set) => ({
  selectedJobId: null,
  activeJobId: null,
  inspectorTab: 'references',
  mobileView: 'compose',
  showHidden: false,
  showExperimental: readPref(PREF_SHOW_EXPERIMENTAL) === '1',
  tourStep: null,
  tourDone: readPref(PREF_TOUR_DONE) === '1',
  selectJob: (selectedJobId) => set({ selectedJobId }),
  setActiveJob: (activeJobId) => set({ activeJobId, selectedJobId: activeJobId }),
  setInspectorTab: (inspectorTab) => set({ inspectorTab }),
  setMobileView: (mobileView) => set({ mobileView }),
  setShowHidden: (showHidden) => set({ showHidden }),
  setShowExperimental: (showExperimental) => {
    writePref(PREF_SHOW_EXPERIMENTAL, showExperimental ? '1' : null)
    set({ showExperimental })
  },
  openTour: (step = 0) => set({ tourStep: step }),
  setTourStep: (tourStep) => set({ tourStep }),
  closeTour: () => {
    writePref(PREF_TOUR_DONE, '1')
    set({ tourStep: null, tourDone: true })
  },
}))
