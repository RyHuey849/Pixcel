import { BackendStatus } from './components/BackendStatus'
import { ParsePanel } from './components/ParsePanel'
import './App.css'

// Composition only - the upload flow and the connectivity check each own their
// state, so App stays a layout shell as later milestones add to it.

function App() {
  return (
    <main className="app">
      <header>
        <h1>Pixcel</h1>
        <p className="subtitle">MapleStory screenshot OCR</p>
        <BackendStatus />
      </header>

      <ParsePanel />
    </main>
  )
}

export default App
