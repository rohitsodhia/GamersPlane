"use client";

import { siteLinkItems, loggedInLinkItems } from "./util";
import hamburger_menu from "/src/images/hamburger_menu.svg";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

export default function Nav() {
    const [openMenu, setOpenMenu] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);
    const linkClasses =
        "px-2 py-1 lg:p-2 text-right lg:text-left border border-slate-200 last:border-0 hover:bg-slate-200 lg:hover:bg-transparent lg:border-0";

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
            <div className="hidden lg:block border-l border-black mx-2" />
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

    const handleClickOutside = (event: MouseEvent) => {
        if (
            menuRef.current &&
            !menuRef.current.parentElement?.contains(event.target as Node)
        ) {
            setOpenMenu(false);
        }
    };

    useEffect(() => {
        document.addEventListener("click", handleClickOutside);
        return () => {
            document.removeEventListener("click", handleClickOutside);
        };
    }, []);

    return (
        <nav className="w-full h-min">
            <div className="relative flex justify-end">
                <Image
                    src={hamburger_menu}
                    alt="Hamburger menu icon"
                    className="lg:hidden cursor-pointer"
                    onClick={() => setOpenMenu(!openMenu)}
                />
                <div
                    className={`${
                        !openMenu ? "hidden" : ""
                    } absolute top-full right-0 bg-white lg:bg-transparent border border-black lg:border-0 lg:relative lg:flex flex flex-col lg:flex-row justify-end lg:gap-1`}
                    ref={menuRef}
                >
                    {links}
                    {accessLinks}
                </div>
            </div>
        </nav>
    );
}
