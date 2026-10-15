import React, {useEffect, useState} from 'react'
import { Link } from 'react-router-dom'

export default function Listings(){
  const [listings, setListings] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    fetch('/api/motorcycles/')
      .then(r=>r.json())
      .then(data=>{ setListings(data.results || data); setLoading(false) })
      .catch(err=>{ console.error(err); setLoading(false) })
  },[])

  if (loading) return <div className="mm-wrap">Loading auctions…</div>

  return (
    <div className="mm-wrap">
      <nav className="mm-nav">
        <Link to="/">Home</Link>
        <Link to="/market">Auctions</Link>
      </nav>
      <h1 className="mm-brand">Live <span>auctions</span></h1>
      <p className="mm-lede">Motorcycle listings from the MotorMarket API</p>
      <div className="mm-grid">
        {listings.map(l=> (
          <article key={l.id} className="mm-card">
            {l.thumbnail && <img src={l.thumbnail} alt={l.title} />}
            <h3>{l.title}</h3>
            <div className="meta">{l.make} · {l.year}</div>
            <div className="price">Rp {l.start_price}</div>
          </article>
        ))}
      </div>
    </div>
  )
}
