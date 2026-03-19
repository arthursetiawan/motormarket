import React, {useEffect, useState} from 'react'

export default function Listings(){
  const [listings, setListings] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    fetch('/api/motorcycles/')
      .then(r=>r.json())
      .then(data=>{ setListings(data.results || data); setLoading(false) })
      .catch(err=>{ console.error(err); setLoading(false) })
  },[])

  if (loading) return <div style={{padding:20}}>Loading...</div>

  return (
    <div style={{padding:20}}>
      <h1>Listings</h1>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))',gap:12}}>
        {listings.map(l=> (
          <div key={l.id} style={{border:'1px solid #ddd',padding:12,borderRadius:8}}>
            {l.thumbnail && <img src={l.thumbnail} style={{width:'100%',height:140,objectFit:'cover',borderRadius:6}} alt={l.title} />}
            <h3>{l.title}</h3>
            <div style={{color:'#666'}}>{l.make} • {l.year}</div>
            <div style={{fontWeight:700}}>Rp {l.start_price}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
