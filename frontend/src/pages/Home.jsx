import React from 'react'
import { Link } from 'react-router-dom'

export default function Home(){
  return (
    <div className="mm-wrap">
      <nav className="mm-nav">
        <Link to="/">Home</Link>
        <Link to="/market">Auctions</Link>
      </nav>
      <h1 className="mm-brand">Motor<span>Market</span></h1>
      <p className="mm-lede">Frontend scaffold — primary UI lives in Django templates. Browse auctions via the API below.</p>
      <Link to="/market" style={{
        display: 'inline-block',
        background: 'var(--blue-600)',
        color: '#fff',
        fontWeight: 700,
        padding: '10px 18px',
        borderRadius: 6,
        textDecoration: 'none',
      }}>Browse auctions</Link>
    </div>
  )
}
