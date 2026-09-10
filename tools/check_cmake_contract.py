#!/usr/bin/env python3
"""POSIX configure-only package contract check using a fake installed SDK.

The fake toolchain uses /usr/bin/true and skips compiler identification. No
compiler, dependency installation, native build or binary test is executed.
"""
import json, os, pathlib, shutil, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='openms4-py-contract-') as td:
    base=pathlib.Path(td); src=base/'source'; src.mkdir(); prefix=base/'sdk'; prefix.mkdir(); modules=base/'modules'; modules.mkdir()
    for p in root.iterdir():
        if p.name != 'dependencies.lock.json': (src/p.name).symlink_to(p, target_is_directory=p.is_dir())
    (src/'dependencies.lock.json').write_text(json.dumps({'dependencies':{name:{'version':'4.0.0','source_revision':'1'*40} for name in ['OpenMS','OpenMSTestData']}}))
    share=prefix/'share/OpenMS/4.0.0'; (share/'CHEMISTRY').mkdir(parents=True); (share/'CHEMISTRY/unimod.xml').write_text('<fixture/>')
    (share/'test-data/core').mkdir(parents=True); topp=prefix/'share/topp'; topp.mkdir(parents=True)
    for name in ['OpenMS','OpenMSTestData','nanobind']:
        directory=prefix/'lib/cmake'/name; directory.mkdir(parents=True)
        version='2.10.0' if name=='nanobind' else '4.0.0'
        (directory/f'{name}ConfigVersion.cmake').write_text(f'set(PACKAGE_VERSION "{version}")\nif(PACKAGE_FIND_VERSION STREQUAL PACKAGE_VERSION)\nset(PACKAGE_VERSION_COMPATIBLE TRUE)\nset(PACKAGE_VERSION_EXACT TRUE)\nendif()\n')
    (prefix/'lib/cmake/OpenMS/OpenMSConfig.cmake').write_text(f'''
set(OpenMS_VERSION 4.0.0)
set(OpenMS_SOURCE_REVISION {'1'*40})
set(OpenMS_SHARE_DIR "{share}")
set(OpenMS_TEST_DATA_DIR "{share}/test-data/core")
foreach(t Core OpenSwathAlgo)
  add_library(OpenMS::${{t}} SHARED IMPORTED)
  set_target_properties(OpenMS::${{t}} PROPERTIES IMPORTED_LOCATION "{prefix}/lib/${{t}}.dylib")
endforeach()
add_library(OpenMS::Arrow INTERFACE IMPORTED)
add_library(Eigen3::Eigen INTERFACE IMPORTED)
''')
    (prefix/'lib/cmake/OpenMSTestData/OpenMSTestDataConfig.cmake').write_text(f'set(OpenMSTestData_VERSION 4.0.0)\nset(OpenMSTestData_SOURCE_REVISION {"1"*40})\nset(OpenMSTestData_TOPP_DIR "{topp}")\n')
    (prefix/'lib/cmake/nanobind/nanobindConfig.cmake').write_text('''function(nanobind_add_module name)
set(sources)
foreach(arg IN LISTS ARGN)
if(arg MATCHES "\\\\.cpp$")
list(APPEND sources "${arg}")
endif()
endforeach()
add_library(${name} MODULE ${sources})
endfunction()
''')
    python=base/'fake-python'; python.write_text(f'#!/bin/sh\nprintf "%s\\n" "{prefix}/lib/cmake/nanobind"\n'); python.chmod(0o755)
    (modules/'FindPython.cmake').write_text(f'set(Python_FOUND TRUE)\nset(Python_EXECUTABLE "{python}")\nset(Python_VERSION 3.12)\n')
    toolchain=base/'toolchain.cmake'; toolchain.write_text('''set(CMAKE_CXX_COMPILER "/usr/bin/true")
set(CMAKE_CXX_COMPILER_ID "Clang")
set(CMAKE_CXX_COMPILER_VERSION "17.0.0")
set(CMAKE_CXX_COMPILER_ID_RUN TRUE)
set(CMAKE_CXX_COMPILER_FORCED TRUE)
set(CMAKE_CXX_COMPILER_WORKS TRUE)
''')
    results=[]
    for name,tests,revision in [('normal',False,'1'*40),('tests',True,'1'*40),('wrong-revision',False,'2'*40)]:
        lock=json.loads((src/'dependencies.lock.json').read_text()); lock['dependencies']['OpenMS']['source_revision']=revision
        (src/'dependencies.lock.json').write_text(json.dumps(lock))
        cmd=['cmake','-S',str(src),'-B',str(base/name),f'-DCMAKE_TOOLCHAIN_FILE={toolchain}',f'-DCMAKE_MODULE_PATH={modules}',f'-DCMAKE_PREFIX_PATH={prefix}','-DPYOPENMS_GENERATE_STUBS=OFF',f'-DPYOPENMS_BUILD_TESTING={"ON" if tests else "OFF"}']
        result=subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ok=(result.returncode==0) if name!='wrong-revision' else (result.returncode!=0 and 'SDK revision mismatch' in result.stdout)
        print(name, 'PASS' if ok else 'FAIL', result.returncode)
        print(result.stdout[-2500:])
        results.append(ok)
        if tests and result.returncode==0:
            listing=subprocess.run(['ctest','--test-dir',str(base/name),'-N'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            print(listing.stdout)
            results.append('Total Tests: 4' in listing.stdout)
    if not all(results): raise SystemExit(1)
