"use client";

import { siteLinkItems, loggedInLinkItems } from "./util";
import Link from "next/link";
import { useEffect } from "react";

export default function Nav() {
    const linkClasses = "p-2";

    const links = Object.keys(siteLinkItems).map((title) => {
        return (
            <Link
                href={siteLinkItems[title]}
                key={title}
                className={`${linkClasses} font-semibold`}
            >
                {title}
            </Link>
        );
    });

    const accessLinks = (
        <>
            <div className="border-l border-black mx-2" />
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
        <nav className="w-full h-min flex justify-end gap-1">
            {links}
            {accessLinks}
        </nav>
    );
}
