"use client";

import Nav from "./nav";
import gp_logo from "/src/images/logo.svg";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export default function Header() {
    const stdHeaderHeight = 70,
        fullHeaderHeight = 120,
        stdImageHeight = 53,
        fullImageHeight = 100;

    const pathname = usePathname();

    const useStdSize = (): boolean =>
        pathname !== "/" || window.scrollY > 50 || window.innerWidth <= 1024;

    const [headerHeight, setHeaderHeight] = useState<number>(
        useStdSize() ? stdHeaderHeight : fullHeaderHeight
    );
    const [imgHeight, setImgHeight] = useState<number>(
        useStdSize() ? stdImageHeight : fullImageHeight
    );

    const updateClasses = () => {
        if (useStdSize()) {
            setHeaderHeight(stdHeaderHeight);
            setImgHeight(stdImageHeight);
        } else {
            setHeaderHeight(fullHeaderHeight);
            setImgHeight(fullImageHeight);
        }
    };

    useEffect(() => {
        if (pathname === "/") {
            updateClasses();
            document.addEventListener("scroll", updateClasses);
            window.addEventListener("resize", updateClasses);
        } else {
            setHeaderHeight(stdHeaderHeight);
            document.removeEventListener("scroll", updateClasses);
            window.removeEventListener("resize", updateClasses);
        }
    }, [pathname]);

    return (
        <header
            id="site_header"
            className="transition-[height] fixed top-0 left-0 w-full z-[100] bg-header-gray shadow-[0_1px_20px_1px_#777] px-4 py-2"
            style={{ height: `${headerHeight}px` }}
        >
            <div className="flex justify-center items-center w-full max-w-screen-xl mx-auto">
                <Link
                    href="/"
                    className="transition-[height] relative w-[250px]"
                    style={{ height: `${imgHeight}px` }}
                >
                    <Image
                        className="object-contain object-left-top"
                        src={gp_logo}
                        alt="Gamers' Plane Logo"
                        fill={true}
                    />
                </Link>
                <Nav />
            </div>
        </header>
    );
}
