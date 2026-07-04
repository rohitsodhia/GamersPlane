import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/systems')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/systems"!</div>
}
