type PagePlaceholderProps = {
  title: string
  description: string
}

export default function PagePlaceholder({ title, description }: PagePlaceholderProps) {
  return (
    <section>
      <h1>{title}</h1>
      <p>{description}</p>
      <p className="placeholder-note">Em construção.</p>
    </section>
  )
}
