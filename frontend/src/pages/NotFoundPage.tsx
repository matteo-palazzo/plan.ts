import { Link } from "react-router";
import { EmptyState } from "../components/ui";

export function NotFoundPage() {
  return (
    <EmptyState title="Pagina non trovata" action={<Link to="/">Torna alla dashboard</Link>}>
      L'indirizzo non corrisponde a nessuna sezione dell'app.
    </EmptyState>
  );
}
