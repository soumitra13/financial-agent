import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Navigation from './components/Navigation'
import ApiKeyModal from './components/ApiKeyModal'
import Home from './pages/Home'
import Terminal from './pages/Terminal'
import Intelligence from './pages/Intelligence'
import Vault from './pages/Vault'
import Metrics from './pages/Metrics'
import { getApiKey } from './api/client'
import './styles/globals.css'

export default function App() {
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    if (!getApiKey()) setShowModal(true)
  }, [])

  return (
    <BrowserRouter>
      <div className="scanlines" style={{ display:'flex', minHeight:'100vh', width:'100%' }}>
        <Navigation />
        <Routes>
          <Route path="/"            element={<Home />} />
          <Route path="/terminal"    element={<Terminal />} />
          <Route path="/intelligence" element={<Intelligence />} />
          <Route path="/metrics"     element={<Metrics />} />
          <Route path="/vault"       element={<Vault />} />
        </Routes>
        <AnimatePresence>
          {showModal && <ApiKeyModal onClose={() => setShowModal(false)} />}
        </AnimatePresence>
      </div>
    </BrowserRouter>
  )
}
