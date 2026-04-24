"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  LayoutDashboard,
  PlusCircle,
  Video,
  BarChart3,
  Settings,
  LogOut,
  PlayCircle as Youtube,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/new-video", label: "New Video", icon: PlusCircle },
  { href: "/my-videos", label: "My Videos", icon: Video },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { email, signOut } = useAuth();

  const handleSignOut = () => {
    signOut();
    router.push("/");
  };

  const handleNavClick = () => {
    // Close sidebar on mobile after navigation
    onClose();
  };

  return (
    <aside
      className={cn(
        "w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full",
        "fixed left-0 top-0 bottom-0 z-50",
        "transform transition-transform duration-300 ease-in-out",
        // Mobile: slide in/out; Desktop: always visible
        isOpen ? "translate-x-0" : "-translate-x-full",
        "md:translate-x-0"
      )}
    >
      {/* Logo + mobile close button */}
      <div className="px-6 py-5 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center">
            <Youtube className="w-5 h-5 text-white" />
          </div>
          <span className="text-white font-bold text-lg">Autopilot</span>
        </div>
        {/* Close button — mobile only */}
        <button
          onClick={onClose}
          className="md:hidden p-1 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition"
          aria-label="Close menu"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              onClick={handleNavClick}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition",
                active
                  ? "bg-red-600 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-gray-800">
        <div className="px-3 py-2 mb-1">
          <p className="text-xs text-gray-500">Signed in as</p>
          <p className="text-sm text-gray-300 truncate">{email}</p>
        </div>
        <button
          onClick={handleSignOut}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 transition"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
