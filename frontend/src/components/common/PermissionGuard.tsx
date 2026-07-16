import { ReactNode } from "react";
import { useAuth } from "@/lib/AuthContext";

type Props = {
  permission: string;
  children: ReactNode;
};

export default function PermissionGuard({ permission, children }: Props) {
  const { user } = useAuth();
  if (!user?.permissions.includes(permission)) return null;
  return <>{children}</>;
}
