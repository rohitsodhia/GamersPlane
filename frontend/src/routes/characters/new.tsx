import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/characters/new')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/characters/new"!</div>
}
