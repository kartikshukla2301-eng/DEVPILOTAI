import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { Button, EmptyState } from "../components/ui";

export default function NotFound() {
  return (
    <EmptyState icon={<Compass className="h-6 w-6" />} title="Page not found" description="The page you were looking for does not exist or was moved."
      action={<Link to="/dashboard"><Button>Back to dashboard</Button></Link>} />
  );
}
