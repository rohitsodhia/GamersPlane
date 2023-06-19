"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function Nav() {
    const linkClasses = "p-2";

    const navLinkItems: { [key: string]: string } = {
        Tools: "/tools",
        Systems: "/systems",
        Characters: "/characters",
        Games: "/games",
        Forums: "/forums",
        "The Gamers": "/gamers",
        Links: "links",
    };
    const loggedInLinkItems = ["Characters", "The Gamers"];

    const links = Object.keys(navLinkItems).map((title) => {
        const extraClasses = title === "Links" ? "mr-2" : "";
        return (
            <Link
                href={navLinkItems[title]}
                key={title}
                className={`${linkClasses} font-semibold ${extraClasses}`}
            >
                {title}
            </Link>
        );
    });

    const accessLinks = (
        <>
            <div className="border-l border-black mr-2" />
            <Link href="/register" className={`${linkClasses}`}>
                Register
            </Link>
            <Link
                href="/login"
                className={`${linkClasses} text-gp-red font-semibold`}
            >
                Login
            </Link>
        </>
    );

    return (
        <nav className="w-full h-min flex justify-end">
            {links}
            {accessLinks}
        </nav>
    );
}
